// @vitest-environment jsdom
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, cleanup, waitFor, fireEvent } from "@testing-library/svelte";

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

const ledger = [
  {
    id: "l1",
    entry_type: "credit",
    amount: 100,
    balance_after: 100,
    reference_type: "quest",
    reference_id: "q1",
    description: "Hadiah quest #1",
    created_at: "2026-01-01T00:00:00Z",
  },
  {
    id: "l2",
    entry_type: "debit",
    amount: 20,
    balance_after: 80,
    reference_type: "withdrawal",
    reference_id: "w1",
    description: null,
    created_at: "2026-01-02T00:00:00Z",
  },
];

const rewards = [
  {
    id: "r1",
    reward_key: "quest:q1",
    reward_type: "quest",
    rank: 1,
    amount: 50,
    status: "confirmed",
    created_at: "2026-01-01T00:00:00Z",
  },
];

describe("wallet ledger — localized labels and description", () => {
  beforeEach(() => {
    cleanup();
    get.mockReset();
    auth.setUser(student);
    get.mockImplementation((path: string) => {
      if (path.startsWith("/wallet/ledger")) return Promise.resolve(ledger);
      if (path.startsWith("/wallet/assets"))
        return Promise.resolve({ assets: [{ asset: "OPT", balance: 80 }] });
      if (path.startsWith("/wallet/rewards")) return Promise.resolve(rewards);
      if (path.startsWith("/wallet/withdrawals")) return Promise.resolve([]);
      if (path.startsWith("/wallet")) return Promise.resolve({ available: 80, pending: 0 });
      if (path.startsWith("/blockchain/transactions")) return Promise.resolve([]);
      if (path.startsWith("/blockchain/status"))
        return Promise.resolve({ paused: false, chain_id: 31337 });
      return Promise.resolve([]);
    });
  });
  afterEach(() => auth.setUser(null));

  it("renders localized entry-type and reference labels", async () => {
    render(WalletPage);
    await waitFor(() => expect(screen.getByText("Buku besar")).toBeTruthy());
    // credit → "Masuk", reference quest → "Hadiah quest".
    expect(screen.getByText("Masuk")).toBeTruthy();
    expect(screen.getByText("Keluar")).toBeTruthy();
    expect(screen.getAllByText("Hadiah quest").length).toBeGreaterThan(0);
    expect(screen.getByText("Penarikan")).toBeTruthy();
  });

  it("shows the entry description when present", async () => {
    render(WalletPage);
    await waitFor(() => expect(screen.getByText("Hadiah quest #1")).toBeTruthy());
  });

  it("signs the amount by entry type", async () => {
    render(WalletPage);
    await waitFor(() => expect(screen.getByText("Buku besar")).toBeTruthy());
    expect(screen.getByText("+100")).toBeTruthy();
    expect(screen.getByText("-20")).toBeTruthy();
  });

  it("localizes reward types in the rewards list", async () => {
    render(WalletPage);
    await waitFor(() => expect(screen.getByText("Hadiah terbaru")).toBeTruthy());
    // reward_type "quest" → "Hadiah quest" (also appears in the ledger, so use getAll).
    expect(screen.getAllByText("Hadiah quest").length).toBeGreaterThan(0);
  });

  it("shows a retry when the wallet itself fails to load", async () => {
    get.mockImplementation((path: string) => {
      if (path === "/wallet") return Promise.reject(new Error("boom"));
      return Promise.resolve([]);
    });
    render(WalletPage);

    // The wallet summary is the primary fetch; a failure must be recoverable.
    const retry = await screen.findByRole("button", { name: /Coba lagi/ });
    get.mockImplementation((path: string) => {
      if (path === "/wallet") return Promise.resolve({ available: 80, pending: 0 });
      if (path.startsWith("/wallet/withdrawals"))
        return Promise.resolve({ items: [], has_more: false });
      if (path.startsWith("/wallet/assets")) return Promise.resolve([]);
      if (path.startsWith("/wallet/ledger")) return Promise.resolve({ items: [], has_more: false });
      if (path.startsWith("/wallet/rewards"))
        return Promise.resolve({ items: [], has_more: false });
      if (path.startsWith("/blockchain/transactions")) return Promise.resolve([]);
      if (path.startsWith("/blockchain/status"))
        return Promise.resolve({ paused: false, chain_id: 31337 });
      return Promise.resolve([]);
    });
    await fireEvent.click(retry);
    await waitFor(() => expect(screen.getByText("Tersedia")).toBeTruthy(), { timeout: 3000 });
  });
});
