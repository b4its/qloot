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

import BlockchainPage from "$routes-panel/admin/blockchain/+page.svelte";
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

const status = {
  dry_run: true,
  network: "local",
  chain_id: 31337,
  token_id: 1,
  confirmations_required: 3,
  treasury_address: "0xtreasury",
  assets: {
    OPT: { name: "OryphemToken", symbol: "OPT", role: "reward", address: "0xopt" },
    QTC: { name: "QuestToken", symbol: "QTC", role: "fee", address: "0xqtc" },
  },
};

const contract = { assets: {}, treasury: "0xtreasury", deployments: [] };

const allocations = [
  { id: "al1", reward_key: "quest:1", user_id: "u1aaaaaa", amount: 10, status: "confirmed" },
  { id: "al2", reward_key: "quest:2", user_id: "u2bbbbbb", amount: 20, status: "failed" },
  { id: "al3", reward_key: "task:1", user_id: "u3cccccc", amount: 5, status: "pending" },
];

describe("admin blockchain hub — allocation metrics and control confirmation", () => {
  beforeEach(() => {
    cleanup();
    get.mockReset();
    post.mockReset();
    auth.setUser(admin);
    get.mockImplementation((path: string) => {
      if (path.startsWith("/blockchain/status")) return Promise.resolve(status);
      if (path.startsWith("/blockchain/contract")) return Promise.resolve(contract);
      if (path.startsWith("/blockchain/allocations")) return Promise.resolve(allocations);
      return Promise.resolve([]);
    });
    post.mockResolvedValue({});
  });
  afterEach(() => auth.setUser(null));

  it("renders the allocation metrics", async () => {
    render(BlockchainPage);
    await waitFor(() => expect(screen.getByText("Alokasi Hadiah Terbaru")).toBeTruthy());
    // 10 + 20 + 5 = 35 OPT total.
    expect(document.querySelector('[data-role="allocated-total"]')?.textContent?.trim()).toBe("35");
  });

  it("confirms before pausing an asset", async () => {
    render(BlockchainPage);
    await waitFor(() => expect(screen.getByRole("button", { name: /Jeda aset/ })).toBeTruthy());

    await fireEvent.click(screen.getByRole("button", { name: /Jeda aset/ }));
    expect(screen.getByText("Jeda Aset On-Chain")).toBeTruthy();
    expect(post).not.toHaveBeenCalled();

    const confirm = document.querySelector('[data-role="confirm-control"]') as HTMLButtonElement;
    await fireEvent.click(confirm);
    await waitFor(() => expect(post).toHaveBeenCalledWith("/admin/blockchain/pause?asset=OPT"));
  });
});
