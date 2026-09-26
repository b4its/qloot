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
vi.mock("$app/navigation", () => ({ goto: vi.fn() }));

import DashboardPage from "$routes-site/dashboard/+page.svelte";
import { auth } from "../src/lib/stores/auth";

const student = {
  id: "u-1",
  email: "s@x.com",
  full_name: "Siswa Satu",
  is_active: true,
  chain_user_ref: "0x0",
  created_at: "2026-01-01T00:00:00Z",
  roles: ["student"],
  class_code: "1A",
  class_type: "IPA",
};

describe("dashboard — next goals widget", () => {
  beforeEach(() => {
    cleanup();
    get.mockReset();
    auth.setUser(student);
    get.mockImplementation((path: string) => {
      if (path.startsWith("/notifications/page"))
        return Promise.resolve({ items: [], total: 3, unread: 3, kind_counts: {} });
      if (path === "/badges/progress")
        return Promise.resolve([
          {
            badge: {
              code: "room_regular",
              name: "Room Regular",
              description: "Joined 5 rooms",
              icon: "🎪",
              points: 20,
              rarity: "rare",
            },
            current: 4,
            target: 5,
            unlocked: false,
          },
          {
            badge: {
              code: "first_quest",
              name: "First Quest",
              description: "x",
              icon: "🎯",
              points: 10,
              rarity: "common",
            },
            current: 1,
            target: 1,
            unlocked: true,
          },
        ]);
      if (path === "/gamification/me") return Promise.resolve(null);
      return Promise.resolve([]);
    });
  });
  afterEach(() => auth.setUser(null));

  it("shows the unread count and the nearest locked badge", async () => {
    render(DashboardPage);
    await waitFor(() =>
      expect(document.querySelector('[data-role="unread-count"]')?.textContent?.trim()).toBe("3"),
    );
    expect(screen.getByText("Room Regular")).toBeTruthy();
    // The unlocked badge is not a "next goal".
    expect(screen.queryByText("First Quest")).toBeNull();
    expect(screen.getByText("4/5")).toBeTruthy();
  });
});
