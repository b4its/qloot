import { writable } from "svelte/store";
import type { User } from "$lib/types";
import { api } from "$lib/api/client";

interface AuthState {
  user: User | null;
  loading: boolean;
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
        const user = await api.get<User>("/auth/me");
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
