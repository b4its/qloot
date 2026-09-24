// @vitest-environment jsdom
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, cleanup, waitFor } from "@testing-library/svelte";

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

import BadgesPage from "$routes-site/badges/+page.svelte";
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

describe("badges page — rarity tiers (GAME-13)", () => {
  beforeEach(() => {
    cleanup();
    get.mockReset();
    auth.setUser(student);
    get.mockImplementation((path: string) => {
      if (path === "/badges")
        return Promise.resolve([
          {
            code: "first_quest",
            name: "First Quest",
            description: "d",
            icon: "🎯",
            points: 10,
            rarity: "common",
          },
          {
            code: "perfect_exam",
            name: "Perfect Score",
            description: "d",
            icon: "🌟",
            points: 40,
            rarity: "epic",
          },
        ]);
      if (path === "/me/badges") return Promise.resolve([]);
      return Promise.resolve([]);
    });
  });
  afterEach(() => auth.setUser(null));

  it("renders each badge's rarity label", async () => {
    render(BadgesPage);
    await waitFor(() => expect(screen.getByText("First Quest")).toBeTruthy());
    expect(screen.getByText("Umum")).toBeTruthy();
    expect(screen.getByText("Epik")).toBeTruthy();
  });

  it("orders rarer badges first", async () => {
    render(BadgesPage);
    await waitFor(() => expect(screen.getByText("First Quest")).toBeTruthy());
    const headings = screen.getAllByRole("heading", { level: 2 }).map((h) => h.textContent);
    expect(headings.indexOf("Perfect Score")).toBeLessThan(headings.indexOf("First Quest"));
  });
});
