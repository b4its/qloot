// @vitest-environment jsdom
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, fireEvent, cleanup, waitFor } from "@testing-library/svelte";

vi.mock("$app/navigation", () => ({ goto: vi.fn() }));

const get = vi.fn();
const post = vi.fn();
vi.mock("../src/lib/api/client", () => ({
  API_BASE: "http://localhost:8000",
  ApiError: class ApiError extends Error {
    status = 0;
  },
  api: {
    get: (...a: unknown[]) => get(...a),
    post: (...a: unknown[]) => post(...a),
    put: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
}));

import AdminRewards from "$routes-panel/admin/rewards/+page.svelte";
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

function reward(over: Record<string, unknown> = {}) {
  return {
    id: "r1",
    reward_key: "quest:q1:rank1",
    reward_type: "quest",
    amount: 10,
    status: "confirmed",
    user_id: "u1",
    created_at: "2026-01-01T00:00:00Z",
    ...over,
  };
}

const rewards = [
  reward({ id: "r1", status: "confirmed" }),
  reward({ id: "r2", reward_key: "quest:q2:rank1", status: "pending", amount: 20 }),
  reward({ id: "r3", reward_key: "task:t1", status: "failed", amount: 5 }),
];

describe("admin rewards — metrics, filters, and cancel confirmation", () => {
  beforeEach(() => {
    cleanup();
    get.mockReset();
    post.mockReset();
    auth.setUser(admin);
    get.mockImplementation((path: string) =>
      path.startsWith("/admin/rewards") ? Promise.resolve(rewards) : Promise.resolve([]),
    );
    post.mockResolvedValue({});
  });
  afterEach(() => auth.setUser(null));

  it("renders the status metrics", async () => {
    render(AdminRewards);
    await waitFor(() => expect(screen.getAllByText("Terkonfirmasi").length).toBeGreaterThan(0));
    expect(document.querySelector('[data-role="confirmed-count"]')?.textContent?.trim()).toBe("1");
  });

  it("filters by status", async () => {
    render(AdminRewards);
    await waitFor(() =>
      expect(document.querySelector('[data-role="confirmed-count"]')).toBeTruthy(),
    );

    // Click the "Gagal" filter chip (second "Gagal" is the metric label).
    const chips = screen
      .getAllByRole("button", { name: "Gagal" })
      .filter((b) => b.classList.contains("rounded-xs"));
    await fireEvent.click(chips[0]);
    await waitFor(() => {
      const rows = document.querySelectorAll("tbody tr");
      expect(rows.length).toBe(1);
    });
  });

  it("confirms before cancelling a pending reward", async () => {
    render(AdminRewards);
    await waitFor(() => expect(document.querySelector("tbody")).toBeTruthy());

    const cancelBtn = screen.getByRole("button", { name: "Batal" });
    await fireEvent.click(cancelBtn);
    expect(screen.getByText("Konfirmasi Batalkan Hadiah")).toBeTruthy();
    expect(post).not.toHaveBeenCalled();

    const confirm = document.querySelector(
      '[data-role="confirm-cancel-reward"]',
    ) as HTMLButtonElement;
    await fireEvent.click(confirm);
    await waitFor(() => expect(post).toHaveBeenCalledWith("/admin/rewards/r2/cancel"));
  });
});
