// @vitest-environment jsdom
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, cleanup, waitFor } from "@testing-library/svelte";

vi.mock("$app/navigation", () => ({ goto: vi.fn() }));

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

import AdminHub from "$routes-panel/admin/+page.svelte";
import { auth } from "../src/lib/stores/auth";

const admin = {
  id: "a1",
  email: "a@x.com",
  full_name: "Admin",
  is_active: true,
  chain_user_ref: "0x0",
  created_at: "2026-01-01T00:00:00Z",
  roles: ["admin"],
};

function user(over: Record<string, unknown> = {}) {
  return {
    id: "u1",
    email: "u@x.com",
    full_name: "User",
    is_active: true,
    chain_user_ref: "0x0",
    created_at: "2026-01-01T00:00:00Z",
    roles: ["student"],
    ...over,
  };
}

function setup(map: Record<string, unknown>) {
  get.mockImplementation((path: string) => {
    for (const [prefix, value] of Object.entries(map)) {
      if (path.startsWith(prefix)) return Promise.resolve(value);
    }
    return Promise.resolve([]);
  });
}

describe("admin hub — status-aware operational overview", () => {
  beforeEach(() => {
    cleanup();
    get.mockReset();
    auth.setUser(admin);
  });
  afterEach(() => auth.setUser(null));

  it("computes operational metrics from the loaded endpoints", async () => {
    setup({
      "/admin/users": [user(), user({ id: "u2", roles: ["teacher"] })],
      "/admin/withdrawals": [
        {
          id: "w1",
          user_id: "u1",
          amount: 10,
          status: "requested",
          created_at: "2026-01-01T00:00:00Z",
        },
      ],
      "/admin/rewards": [
        {
          id: "r1",
          reward_key: "k",
          reward_type: "quest",
          amount: 5,
          status: "failed",
          created_at: "2026-01-01T00:00:00Z",
        },
      ],
      "/admin/ledger/negative": [{ account_id: "acc1", user_id: "u1", cached_balance: -5 }],
      "/admin/audit-logs": [],
    });
    render(AdminHub);

    await waitFor(() =>
      expect(document.querySelector('[data-role="active-users"]')?.textContent?.trim()).toBe("2"),
    );
    expect(document.querySelector('[data-role="pending-withdrawals"]')?.textContent?.trim()).toBe(
      "1",
    );
    // Health warning section for the failed reward + negative balance.
    expect(screen.getByText("Perlu tindakan")).toBeTruthy();
  });

  it("shows a live status chip on the withdrawals module", async () => {
    setup({
      "/admin/users": [user()],
      "/admin/withdrawals": [
        {
          id: "w1",
          user_id: "u1",
          amount: 10,
          status: "requested",
          created_at: "2026-01-01T00:00:00Z",
        },
        {
          id: "w2",
          user_id: "u2",
          amount: 10,
          status: "submitted",
          created_at: "2026-01-01T00:00:00Z",
        },
      ],
      "/admin/rewards": [],
      "/admin/ledger/negative": [],
      "/admin/audit-logs": [],
    });
    render(AdminHub);
    await waitFor(() => {
      const mod = document.querySelector('[data-module="/admin/withdrawals"]') as HTMLElement;
      expect(mod?.textContent).toContain("2 menunggu");
    });
  });

  it("shows recent audit activity", async () => {
    setup({
      "/admin/users": [user()],
      "/admin/withdrawals": [],
      "/admin/rewards": [],
      "/admin/ledger/negative": [],
      "/admin/audit-logs": [
        {
          id: "a1",
          action: "user.role_changed",
          actor_id: "a1",
          created_at: "2026-01-01T00:00:00Z",
        },
      ],
    });
    render(AdminHub);
    await waitFor(() => expect(screen.getByText("user.role_changed")).toBeTruthy());
    expect(screen.getByText("Aktivitas terbaru")).toBeTruthy();
  });

  it("marks a module unavailable instead of a healthy status when its fetch fails", async () => {
    get.mockImplementation((path: string) => {
      if (path.startsWith("/admin/ledger/negative")) return Promise.reject(new Error("boom"));
      return Promise.resolve([]);
    });
    render(AdminHub);
    await waitFor(() => {
      const mod = document.querySelector('[data-module="/admin/ledger"]') as HTMLElement;
      expect(mod?.textContent).toContain("Data tak tersedia");
      // Must not claim the ledger is balanced when we could not read it.
      expect(mod?.textContent).not.toContain("Seimbang");
    });
  });
});
