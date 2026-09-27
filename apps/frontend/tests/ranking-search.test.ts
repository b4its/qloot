// @vitest-environment jsdom
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, fireEvent, cleanup, waitFor } from "@testing-library/svelte";

const get = vi.fn();
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
    delete: vi.fn(),
  },
}));

import RankingPage from "$routes-site/ranking/+page.svelte";
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

const entries = [
  { user_id: "u1", rank: 1, score_bp: 9000, opc_earned: 100, display_name: "Andi" },
  { user_id: "u2", rank: 2, score_bp: 7000, opc_earned: 80, display_name: "Bunga" },
  { user_id: "u3", rank: 3, score_bp: 5000, opc_earned: 60, display_name: "Cinta" },
];

describe("ranking page — metrics and name search", () => {
  beforeEach(() => {
    cleanup();
    get.mockReset();
    auth.setUser(student);
    get.mockImplementation((path: string) => {
      if (path.startsWith("/rankings/me"))
        return Promise.resolve({ user_id: "u1", total_score_bp: 9000, opc_balance: 100, rank: 1 });
      if (path.startsWith("/rankings/global")) return Promise.resolve({ scope: "global", entries });
      if (path.startsWith("/gamification/levels")) return Promise.resolve({ entries: [] });
      return Promise.resolve([]);
    });
  });
  afterEach(() => auth.setUser(null));

  it("renders the page metric strip", async () => {
    render(RankingPage);
    await waitFor(() => expect(screen.getByText("Andi")).toBeTruthy());
    // Top 90.0%, avg (90+70+50)/3 = 70.0%.
    expect(document.querySelector('[data-role="top-score"]')?.textContent?.trim()).toBe("90.0%");
    expect(screen.getAllByText("70.0%").length).toBeGreaterThan(0);
  });

  it("filters leaderboard entries by name", async () => {
    render(RankingPage);
    await waitFor(() => expect(screen.getByText("Andi")).toBeTruthy());

    const input = screen.getByLabelText("Cari pengguna") as HTMLInputElement;
    await fireEvent.input(input, { target: { value: "bunga" } });
    await waitFor(() => expect(screen.queryByText("Andi")).toBeNull());
    expect(screen.getByText("Bunga")).toBeTruthy();
  });

  it("shows a no-match row when the search misses", async () => {
    render(RankingPage);
    await waitFor(() => expect(screen.getByText("Andi")).toBeTruthy());

    const input = screen.getByLabelText("Cari pengguna") as HTMLInputElement;
    await fireEvent.input(input, { target: { value: "zzz" } });
    await waitFor(() => expect(screen.getByText(/Tidak ada pengguna yang cocok/)).toBeTruthy());
  });
});
