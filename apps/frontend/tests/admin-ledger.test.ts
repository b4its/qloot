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

import LedgerPage from "$routes-panel/admin/ledger/+page.svelte";
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

describe("admin ledger — health, metrics, search, and reconcile confirmation", () => {
  beforeEach(() => {
    cleanup();
    get.mockReset();
    post.mockReset();
    auth.setUser(admin);
    post.mockResolvedValue({ drifted: [], count: 0 });
  });
  afterEach(() => auth.setUser(null));

  it("shows a healthy banner when there are no negative balances", async () => {
    get.mockResolvedValue([]);
    render(LedgerPage);
    await waitFor(() => expect(screen.getByText("Ledger sehat")).toBeTruthy());
    expect(document.querySelector('[data-role="ledger-health"]')).toBeTruthy();
  });

  it("shows the debt metrics when accounts are negative", async () => {
    get.mockResolvedValue([
      { account_id: "acc1", user_id: "u1aaaaaa", cached_balance: -5, is_in_debt: true },
      { account_id: "acc2", user_id: "u2bbbbbb", cached_balance: -15, is_in_debt: true },
    ]);
    render(LedgerPage);
    await waitFor(() =>
      expect(document.querySelector('[data-role="negative-count"]')?.textContent?.trim()).toBe("2"),
    );
    // 5 + 15 = 20 OPT in debt.
    expect(document.querySelector('[data-role="total-debt"]')?.textContent?.trim()).toBe("20");
  });

  it("confirms before running reconciliation", async () => {
    get.mockResolvedValue([]);
    render(LedgerPage);
    await waitFor(() => expect(screen.getByText("Ledger sehat")).toBeTruthy());

    await fireEvent.click(screen.getByRole("button", { name: "Rekonsiliasi sekarang" }));
    expect(screen.getByText("Jalankan Rekonsiliasi Ledger")).toBeTruthy();
    expect(post).not.toHaveBeenCalled();

    const confirm = document.querySelector('[data-role="confirm-reconcile"]') as HTMLButtonElement;
    await fireEvent.click(confirm);
    await waitFor(() => expect(post).toHaveBeenCalledWith("/admin/ledger/reconcile"));
  });

  it("filters negative accounts by user id", async () => {
    get.mockResolvedValue([
      { account_id: "acc1", user_id: "u1aaaaaa", cached_balance: -5, is_in_debt: true },
      { account_id: "acc2", user_id: "u2bbbbbb", cached_balance: -15, is_in_debt: true },
    ]);
    render(LedgerPage);
    await waitFor(() => expect(document.querySelectorAll("tbody tr").length).toBe(2));

    const input = (await screen.findByLabelText("Cari akun")) as HTMLInputElement;
    await fireEvent.input(input, { target: { value: "u2bbbbbb" } });
    await waitFor(() => expect(document.querySelectorAll("tbody tr").length).toBe(1));
  });
});
