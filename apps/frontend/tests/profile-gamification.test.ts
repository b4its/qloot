// @vitest-environment jsdom
import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, cleanup, waitFor } from "@testing-library/svelte";

const get = vi.fn();
vi.mock("../src/lib/api/client", () => ({
  API_BASE: "http://localhost:8000",
  ApiError: class ApiError extends Error {
    status = 0;
  },
  api: {
    get: (...args: unknown[]) => get(...args),
    post: vi.fn().mockRejectedValue(new Error("offline")),
  },
}));

import ProfilePage from "$routes-site/profile/+page.svelte";
import { auth } from "../src/lib/stores/auth";

const PROFILE = {
  user_id: "u-1",
  xp: 1234,
  level: 4,
  xp_into_level: 234,
  xp_for_next_level: 500,
  progress: 0.468,
  breakdown: { exams: 800, quests: 300, tasks: 120, badges: 14 },
  quest_wins: 2,
  tasks_completed: 3,
  current_streak: 5,
  best_streak: 9,
  last_active_date: "2026-09-24",
};

beforeEach(() => {
  cleanup();
  get.mockReset();
  get.mockImplementation((path: string) => {
    if (path === "/auth/sessions") return Promise.resolve([]);
    if (path === "/gamification/me") return Promise.resolve(PROFILE);
    return Promise.reject(new Error(`unexpected path ${path}`));
  });
  auth.setUser({
    id: "u-1",
    email: "a@b.com",
    full_name: "Test User",
    is_active: true,
    chain_user_ref: "0x1",
    created_at: "2026-01-01T00:00:00Z",
    roles: ["student"],
  });
});

describe("profile gamification card", () => {
  it("renders level, total XP, and breakdown from /gamification/me", async () => {
    render(ProfilePage);

    await waitFor(() => expect(screen.getByText("Progres gamifikasi")).toBeTruthy());

    expect(get).toHaveBeenCalledWith("/gamification/me");
    expect(screen.getByText("4")).toBeTruthy();
    expect(screen.getByText("1,234")).toBeTruthy();
    expect(screen.getByText("Menuju level 5")).toBeTruthy();
    expect(screen.getByText("Ujian 800 XP")).toBeTruthy();
    expect(screen.getByText("Quest 300 XP")).toBeTruthy();
    expect(screen.getByText("Tugas 120 XP")).toBeTruthy();
    expect(screen.getByText("Badge 14 XP")).toBeTruthy();
  });

  it("renders the current and best streak (GAME-05)", async () => {
    render(ProfilePage);
    await waitFor(() => expect(screen.getByText("Progres gamifikasi")).toBeTruthy());
    expect(screen.getByText(/Streak 5 hari/)).toBeTruthy();
    expect(screen.getByText(/Terbaik 9 hari/)).toBeTruthy();
  });
});
