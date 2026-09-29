// @vitest-environment jsdom
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, fireEvent, cleanup, waitFor } from "@testing-library/svelte";

vi.mock("$app/navigation", () => ({ goto: vi.fn() }));

const get = vi.fn();
const del = vi.fn();
vi.mock("../src/lib/api/client", () => ({
  API_BASE: "http://localhost:8000",
  ApiError: class ApiError extends Error {
    status = 0;
  },
  api: {
    get: (...a: unknown[]) => get(...a),
    post: vi.fn(),
    put: vi.fn(),
    patch: vi.fn(),
    delete: (...a: unknown[]) => del(...a),
  },
}));

import ProfilePage from "$routes-site/profile/+page.svelte";
import { auth } from "../src/lib/stores/auth";

const student = {
  id: "u1",
  email: "s@x.com",
  full_name: "Student",
  is_active: true,
  chain_user_ref: "0x0",
  created_at: "2026-01-01T00:00:00Z",
  roles: ["student"],
};

const sessions = [
  {
    id: "s1",
    user_agent: "Chrome on Linux",
    ip_address: "127.0.0.1",
    created_at: "2026-01-01T00:00:00Z",
    expires_at: "2026-02-01T00:00:00Z",
  },
];

describe("profile — active sessions and revoke confirmation", () => {
  beforeEach(() => {
    cleanup();
    get.mockReset();
    del.mockReset();
    auth.setUser(student);
    get.mockImplementation((path: string) => {
      if (path === "/auth/sessions") return Promise.resolve(sessions);
      if (path === "/gamification/me")
        return Promise.resolve({
          user_id: "u1",
          xp: 100,
          level: 2,
          xp_into_level: 10,
          xp_for_next_level: 100,
          progress: 0.1,
          breakdown: { exams: 50, quests: 30, tasks: 10, badges: 10 },
          quest_wins: 0,
          tasks_completed: 0,
          current_streak: 1,
          best_streak: 1,
          last_active_date: "2026-01-01",
        });
      if (path.startsWith("/users/")) return Promise.resolve({ followers: 0, following: 0 });
      return Promise.resolve([]);
    });
    del.mockResolvedValue({});
  });
  afterEach(() => auth.setUser(null));

  it("shows the session count badge", async () => {
    render(ProfilePage);
    await waitFor(() =>
      expect(document.querySelector('[data-role="session-count"]')?.textContent?.trim()).toBe(
        "1 sesi",
      ),
    );
  });

  it("confirms before revoking a session", async () => {
    render(ProfilePage);
    await waitFor(() => expect(screen.getByRole("button", { name: "Cabut" })).toBeTruthy());

    await fireEvent.click(screen.getByRole("button", { name: "Cabut" }));
    expect(screen.getByText("Cabut Sesi")).toBeTruthy();
    expect(del).not.toHaveBeenCalled();

    const confirm = document.querySelector(
      '[data-role="confirm-revoke-session"]',
    ) as HTMLButtonElement;
    await fireEvent.click(confirm);
    await waitFor(() => expect(del).toHaveBeenCalledWith("/auth/sessions/s1"));
  });

  it("shows follow counts, and discloses when they cannot be loaded", async () => {
    get.mockImplementation((path: string) => {
      if (path === "/auth/sessions") return Promise.resolve(sessions);
      if (path === "/gamification/me")
        return Promise.resolve({
          user_id: "u1",
          xp: 0,
          level: 1,
          xp_into_level: 0,
          xp_for_next_level: 100,
          progress: 0,
          breakdown: {},
          quest_wins: 0,
          tasks_completed: 0,
          current_streak: 0,
          best_streak: 0,
          last_active_date: null,
        });
      if (path.startsWith("/users/")) return Promise.reject(new Error("boom"));
      return Promise.resolve([]);
    });

    render(ProfilePage);
    await waitFor(() =>
      expect(screen.getByText(/jumlah pengikut belum dapat dimuat/i)).toBeTruthy(),
    );
  });

  it("loads follow counts once auth resolves after mount (hard refresh)", async () => {
    // Hard refresh: the page mounts while auth is still loading, so $auth.user
    // is null when load() begins. The per-user follow counts must still load
    // once auth settles, not be skipped forever.
    let resolveMe: (u: unknown) => void = () => {};
    const mePromise = new Promise((res) => {
      resolveMe = res;
    });
    // Keep load()'s own first await pending so the component is still mid-load
    // when auth resolves — the exact ordering of a hard refresh.
    let resolveSessions: (s: unknown) => void = () => {};
    const sessionsPromise = new Promise((res) => {
      resolveSessions = res;
    });
    get.mockImplementation((path: string) => {
      if (path.includes("/auth/me")) return mePromise;
      if (path === "/auth/sessions") return sessionsPromise;
      if (path === "/gamification/me")
        return Promise.resolve({
          user_id: "u1",
          xp: 0,
          level: 1,
          xp_into_level: 0,
          xp_for_next_level: 100,
          progress: 0,
          breakdown: {},
          quest_wins: 0,
          tasks_completed: 0,
          current_streak: 0,
          best_streak: 0,
          last_active_date: null,
        });
      if (path.startsWith("/users/")) return Promise.resolve({ followers: 7, following: 3 });
      return Promise.resolve([]);
    });

    auth.setUser(null);
    const loading = auth.load();
    render(ProfilePage);
    // Let load()'s own fetch complete FIRST while auth is still unresolved:
    // its `user?.id` guard then reads null and (on the buggy code) skips the
    // follow fetch forever. Auth resolving afterwards must still trigger it.
    resolveSessions(sessions);
    await new Promise((r) => setTimeout(r, 0));
    resolveMe(student);
    await loading;

    await waitFor(() =>
      expect(get.mock.calls.some((c) => String(c[0]).includes("/users/u1/follow"))).toBe(true),
    );
    expect(await screen.findByText("7")).toBeTruthy();
  });
});
