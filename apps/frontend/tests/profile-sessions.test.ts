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
});
