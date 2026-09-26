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

import AdminWithdrawals from "$routes-panel/admin/withdrawals/+page.svelte";
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

function wd(over: Record<string, unknown> = {}) {
  return {
    id: "w1",
    user_id: "u1aaaaaa",
    destination_address: "0xabcdef1234567890",
    amount: 100,
    fee_amount: 2,
    status: "requested",
    reject_reason: null,
    created_at: "2026-01-01T00:00:00Z",
    ...over,
  };
}

const items = [
  wd({ id: "w1" }),
  wd({ id: "w2", user_id: "u2bbbbbb", destination_address: "0x9999888877776666", amount: 50 }),
];

describe("admin withdrawals — metrics, search, and reject modal", () => {
  beforeEach(() => {
    cleanup();
    get.mockReset();
    post.mockReset();
    auth.setUser(admin);
    get.mockImplementation((path: string) =>
      path.startsWith("/admin/withdrawals") ? Promise.resolve(items) : Promise.resolve([]),
    );
    post.mockResolvedValue({});
  });
  afterEach(() => auth.setUser(null));

  it("renders the pending count and totals", async () => {
    render(AdminWithdrawals);
    await waitFor(() =>
      expect(document.querySelector('[data-role="requested-count"]')?.textContent?.trim()).toBe(
        "2",
      ),
    );
  });

  it("confirms before rejecting and sends the reason", async () => {
    render(AdminWithdrawals);
    await waitFor(() => expect(screen.getAllByRole("button", { name: "Tolak" }).length).toBe(2));

    await fireEvent.click(screen.getAllByRole("button", { name: "Tolak" })[0]);
    expect(screen.getByText("Tolak Permintaan Penarikan")).toBeTruthy();
    expect(post).not.toHaveBeenCalled();

    const reason = screen.getByPlaceholderText("mis. alamat tidak valid") as HTMLInputElement;
    await fireEvent.input(reason, { target: { value: "alamat salah" } });
    const confirm = document.querySelector('[data-role="confirm-reject"]') as HTMLButtonElement;
    await fireEvent.click(confirm);
    await waitFor(() =>
      expect(post).toHaveBeenCalledWith("/admin/withdrawals/w1/reject", { reason: "alamat salah" }),
    );
  });

  it("searches withdrawals by destination address", async () => {
    render(AdminWithdrawals);
    await waitFor(() => expect(screen.getAllByRole("button", { name: "Tolak" }).length).toBe(2));

    const input = screen.getByLabelText("Cari penarikan") as HTMLInputElement;
    await fireEvent.input(input, { target: { value: "9999" } });
    await waitFor(() => expect(document.querySelectorAll("tbody tr").length).toBe(1));
  });

  it("switches the status filter via the tab row", async () => {
    render(AdminWithdrawals);
    await waitFor(() => expect(screen.getByRole("tab", { name: "Disetujui" })).toBeTruthy());

    await fireEvent.click(screen.getByRole("tab", { name: "Disetujui" }));
    await waitFor(() =>
      expect(get.mock.calls.some((c) => String(c[0]).includes("status_filter=approved"))).toBe(
        true,
      ),
    );
  });
});
