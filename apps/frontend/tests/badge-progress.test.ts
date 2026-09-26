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

const catalog = [
  {
    code: "room_regular",
    name: "Room Regular",
    description: "Joined 5 rooms",
    icon: "🎪",
    points: 20,
    rarity: "common",
  },
  {
    code: "first_quest",
    name: "First Quest",
    description: "Completed your first quest",
    icon: "🎯",
    points: 10,
    rarity: "common",
  },
];

describe("badges page — progress toward locked badges", () => {
  beforeEach(() => {
    cleanup();
    get.mockReset();
    auth.setUser(student);
    get.mockImplementation((path: string) => {
      if (path === "/badges") return Promise.resolve(catalog);
      if (path === "/me/badges")
        return Promise.resolve([
          {
            badge: catalog[1],
            awarded_at: "2026-01-02T00:00:00Z",
            meta: null,
          },
        ]);
      if (path === "/badges/progress")
        return Promise.resolve([
          { badge: catalog[0], current: 3, target: 5, unlocked: false },
          { badge: catalog[1], current: 1, target: 1, unlocked: true },
        ]);
      return Promise.resolve([]);
    });
  });
  afterEach(() => auth.setUser(null));

  it("renders a progress bar with current/target for locked badges", async () => {
    render(BadgesPage);
    await waitFor(() => expect(screen.getByText("Room Regular")).toBeTruthy());
    // Locked badge exposes its progress fraction.
    expect(screen.getByText("3/5")).toBeTruthy();
    const bar = screen.getByRole("progressbar", { name: /Room Regular/i });
    expect(bar.getAttribute("aria-valuenow")).toBe("3");
    expect(bar.getAttribute("aria-valuemax")).toBe("5");
  });

  it("labels unlocked vs locked badges via status chips", async () => {
    render(BadgesPage);
    await waitFor(() => expect(screen.getByText("First Quest")).toBeTruthy());
    const statuses = Array.from(document.querySelectorAll('[data-role="status"]')).map(
      (el) => el.textContent?.trim() ?? "",
    );
    expect(statuses.some((s) => s.includes("Diraih"))).toBe(true);
    expect(statuses.some((s) => s.includes("Terkunci"))).toBe(true);
  });

  it("shows the earned count in the overview metric", async () => {
    render(BadgesPage);
    await waitFor(() => expect(screen.getByText("First Quest")).toBeTruthy());
    // 1 of 2 unlocked => 50% completion.
    expect(screen.getByText("50%")).toBeTruthy();
  });
});
