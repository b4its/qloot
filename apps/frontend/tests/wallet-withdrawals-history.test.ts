// @vitest-environment jsdom
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, fireEvent, cleanup, waitFor } from "@testing-library/svelte";

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

vi.mock("../src/lib/stores/opt", () => ({
  opt: { refresh: vi.fn(), subscribe: () => () => {} },
}));

import WalletPage from "$routes-site/wallet/+page.svelte";
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

function wd(over: Record<string, unknown> = {}) {
  return {
    id: "w1",
    amount: 100,
    fee_amount: 2,
    status: "requested",
    destination_address: "0xabcdef1234567890",
    reject_reason: null,
    created_at: "2026-01-01T00:00:00Z",
    ...over,
  };
}

const withdrawals = [
  wd({ id: "w1", status: "requested", amount: 100 }),
  wd({ id: "w2", status: "confirmed", amount: 50 }),
  wd({ id: "w3", status: "rejected", amount: 25, reject_reason: "alamat tidak valid" }),
];

describe("wallet withdrawal history — filter and labels", () => {
  beforeEach(() => {
    cleanup();
    get.mockReset();
    auth.setUser(student);
    get.mockImplementation((path: string) => {
      if (path.startsWith("/wallet/withdrawals")) return Promise.resolve(withdrawals);
      if (path.startsWith("/wallet/assets"))
        return Promise.resolve({ assets: [{ asset: "OPT", balance: 1000 }] });
      if (path.startsWith("/wallet")) return Promise.resolve({ available: 1000, pending: 0 });
      if (path.startsWith("/blockchain/status"))
        return Promise.resolve({ paused: false, chain_id: 31337 });
      if (path.startsWith("/blockchain/transactions")) return Promise.resolve([]);
      return Promise.resolve([]);
    });
  });
  afterEach(() => auth.setUser(null));

  it("shows localized status labels in the withdrawal history", async () => {
    render(WalletPage);
    await waitFor(() => expect(screen.getByText("Riwayat penarikan")).toBeTruthy());
    // statusLabel maps requested → "Menunggu" etc.; at least one localized label shows.
    expect(screen.getAllByText(/Diproses|Selesai|Menunggu/).length).toBeGreaterThan(0);
  });

  it("filters the history to confirmed withdrawals", async () => {
    render(WalletPage);
    await waitFor(() => expect(screen.getByText("Riwayat penarikan")).toBeTruthy());

    await fireEvent.click(screen.getByRole("button", { name: /Selesai \(/ }));
    await waitFor(() => {
      const items = document.querySelectorAll("ul li");
      // Only the confirmed withdrawal (50 OPT) remains in the history list.
      expect(document.body.textContent).toContain("50 OPT");
      expect(document.body.textContent).not.toContain("100 OPT");
    });
  });

  it("shows the reject reason on a rejected withdrawal", async () => {
    render(WalletPage);
    await waitFor(() => expect(screen.getByText("Riwayat penarikan")).toBeTruthy());
    expect(screen.getByText("alamat tidak valid")).toBeTruthy();
  });
});
