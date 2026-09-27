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

import BlockchainTxPage from "$routes-panel/admin/blockchain/transactions/+page.svelte";
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

const txs = [
  {
    id: "t1",
    method: "award",
    status: "confirmed",
    transaction_hash: "0xaaaa",
    confirmation_count: 12,
    created_at: "2026-01-01T00:00:00Z",
  },
  {
    id: "t2",
    method: "burn",
    status: "pending",
    transaction_hash: "0xbbbb",
    confirmation_count: 0,
    created_at: "2026-01-02T00:00:00Z",
  },
];

describe("admin blockchain transactions — metrics, search, and status filter", () => {
  beforeEach(() => {
    cleanup();
    get.mockReset();
    auth.setUser(admin);
    get.mockImplementation((path: string) => {
      if (path.startsWith("/blockchain/transactions/failed")) return Promise.resolve([]);
      if (path.startsWith("/blockchain/transactions")) return Promise.resolve(txs);
      if (path.startsWith("/blockchain/status/admin")) return Promise.resolve({ chain_id: 31337 });
      return Promise.resolve([]);
    });
  });
  afterEach(() => auth.setUser(null));

  it("renders the confirmed/pending metrics", async () => {
    render(BlockchainTxPage);
    await waitFor(() => expect(screen.getByText("award")).toBeTruthy());
    expect(document.querySelector('[data-role="confirmed-count"]')?.textContent?.trim()).toBe("1");
  });

  it("filters by status", async () => {
    render(BlockchainTxPage);
    await waitFor(() => expect(screen.getByText("award")).toBeTruthy());

    await fireEvent.click(screen.getByRole("button", { name: "Tertunda" }));
    await waitFor(() => expect(screen.queryByText("award")).toBeNull());
    expect(screen.getByText("burn")).toBeTruthy();
  });

  it("searches transactions by method", async () => {
    render(BlockchainTxPage);
    await waitFor(() => expect(screen.getByText("award")).toBeTruthy());

    const input = screen.getByLabelText("Cari transaksi") as HTMLInputElement;
    await fireEvent.input(input, { target: { value: "burn" } });
    await waitFor(() => expect(screen.queryByText("award")).toBeNull());
    expect(screen.getByText("burn")).toBeTruthy();
  });
});
