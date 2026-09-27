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

import EventsPage from "$routes-panel/admin/blockchain/events/+page.svelte";
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

const events = [
  {
    name: "RewardPaid",
    transaction_hash: "0xaaaa",
    block_number: 100,
    log_index: 1,
    args: { amount: 10 },
  },
  {
    name: "Transfer",
    transaction_hash: "0xbbbb",
    block_number: 101,
    log_index: 2,
    args: { value: 5 },
  },
];

describe("admin blockchain events — metrics, name filter, search, expand", () => {
  beforeEach(() => {
    cleanup();
    get.mockReset();
    auth.setUser(admin);
    get.mockImplementation((path: string) =>
      path.startsWith("/blockchain/events") ? Promise.resolve(events) : Promise.resolve([]),
    );
  });
  afterEach(() => auth.setUser(null));

  it("renders event metrics", async () => {
    render(EventsPage);
    await waitFor(() => expect(screen.getByText("RewardPaid")).toBeTruthy());
    expect(document.querySelector('[data-role="event-count"]')?.textContent?.trim()).toBe("2");
    expect(document.querySelector('[data-role="name-count"]')?.textContent?.trim()).toBe("2");
  });

  it("requests a filtered list when a name chip is clicked", async () => {
    render(EventsPage);
    await waitFor(() => expect(screen.getByText("RewardPaid")).toBeTruthy());

    await fireEvent.click(screen.getByRole("button", { name: /RewardPaid \(1\)/ }));
    await waitFor(() =>
      expect(get.mock.calls.some((c) => String(c[0]).includes("name=RewardPaid"))).toBe(true),
    );
  });

  it("expands an event to show its args", async () => {
    render(EventsPage);
    await waitFor(() => expect(screen.getByText("RewardPaid")).toBeTruthy());

    const rowBtn = screen.getByText("RewardPaid").closest("button") as HTMLButtonElement;
    await fireEvent.click(rowBtn);
    await waitFor(() => expect(document.body.textContent).toContain("amount"));
    expect(document.body.textContent).toContain("10");
  });
});
