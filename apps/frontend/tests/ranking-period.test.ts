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

describe("ranking page — period selector (GAME-11)", () => {
  beforeEach(() => {
    cleanup();
    get.mockReset();
    auth.setUser(student);
    get.mockImplementation((path: string) => {
      if (path.startsWith("/rankings/me")) {
        const period = new URL(path, "http://x").searchParams.get("period") ?? "all";
        return Promise.resolve({ user_id: "u1", period, total_score_bp: 8000, opc_balance: 10 });
      }
      if (path.startsWith("/rankings/global")) {
        const period = new URL(path, "http://x").searchParams.get("period") ?? "all";
        return Promise.resolve({ scope: "global", period, entries: [] });
      }
      if (path.startsWith("/gamification/levels")) return Promise.resolve({ entries: [] });
      return Promise.resolve([]);
    });
  });
  afterEach(() => auth.setUser(null));

  it("requests period=all by default and switches to weekly on click", async () => {
    render(RankingPage);
    await waitFor(() =>
      expect(get).toHaveBeenCalledWith(expect.stringContaining("/rankings/me?period=all")),
    );

    const weeklyTab = screen.getByRole("tab", { name: /minggu ini/i });
    await fireEvent.click(weeklyTab);

    await waitFor(() => expect(get).toHaveBeenCalledWith(expect.stringContaining("period=weekly")));
  });
});
