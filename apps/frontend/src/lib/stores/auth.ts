import { writable } from "svelte/store";
import type { User } from "$lib/types";
import { api } from "$lib/api/client";

interface AuthState {
  user: User | null;
  loading: boolean;
}

/** Rotate the session when it has less than this many ms of life left. */
const REFRESH_THRESHOLD_MS = 24 * 60 * 60 * 1000; // 1 day

function needsRefresh(user: User | null): boolean {
  if (!user?.session_expires_at) return false;
  const expires = new Date(user.session_expires_at).getTime();
  if (Number.isNaN(expires)) return false;
  return expires - Date.now() < REFRESH_THRESHOLD_MS;
}

function createAuthStore() {
  const { subscribe, set, update } = writable<AuthState>({ user: null, loading: true });

  return {
    subscribe,
    setUser(user: User | null) {
      set({ user, loading: false });
    },
    async load() {
      update((s) => ({ ...s, loading: true }));
      try {
        let user = await api.get<User>("/auth/me");
        // Near-expiry rotation (AUTH-10): refresh the token before it lapses
        // so the session is silently extended instead of dropping the user.
        if (needsRefresh(user)) {
          try {
            user = await api.post<User>("/auth/refresh");
          } catch {
            // Refresh is best-effort; keep the still-valid user if it fails.
          }
        }
        set({ user, loading: false });
      } catch {
        set({ user: null, loading: false });
      }
    },
    async login(email: string, password: string) {
      const user = await api.post<User>("/auth/login", { email, password });
      set({ user, loading: false });
      return user;
    },
    async register(payload: {
      email: string;
      full_name: string;
      password: string;
      role?: string;
      class_code?: string;
      class_type?: string;
    }) {
      const user = await api.post<User>("/auth/register", payload);
      set({ user, loading: false });
      return user;
    },
    async logout() {
      try {
        await api.post("/auth/logout");
      } finally {
        set({ user: null, loading: false });
      }
    },
    /** Revoke every session for the caller ("sign out everywhere"). */
    async logoutAll() {
      try {
        await api.post("/auth/logout-all");
      } finally {
        set({ user: null, loading: false });
      }
    },
  };
}

export const auth = createAuthStore();

export function hasRole(user: User | null, ...roles: string[]): boolean {
  if (!user) return false;
  if (user.roles.includes("admin")) return true;
  return roles.some((r) => user.roles.includes(r));
}
