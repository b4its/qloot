// @vitest-environment jsdom
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, fireEvent, cleanup, waitFor } from "@testing-library/svelte";

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
vi.mock("$app/navigation", () => ({ goto: vi.fn() }));

import AdminLeaderboardsPage from "$routes-panel/admin/leaderboards/+page.svelte";
import { auth } from "../src/lib/stores/auth";

const admin = {
  id: "a1",
  email: "admin@x.com",
  full_name: "Admin",
  is_active: true,
  chain_user_ref: "0x0",
  created_at: "2026-01-01T00:00:00Z",
  roles: ["admin"],
};

describe("admin leaderboards page (GAME-10)", () => {
  beforeEach(() => {
    cleanup();
    get.mockReset();
    post.mockReset();
    auth.setUser(admin);
    get.mockResolvedValue([
      {
        id: "lb1",
        scope: "global",
        scope_id: null,
        period: "all",
        is_materialized: true,
        updated_at: "2026-09-24T00:00:00Z",
      },
    ]);
  });
  afterEach(() => auth.setUser(null));

  it("lists existing snapshots and refreshes the global board via confirmation", async () => {
    post.mockResolvedValue({ materialized: 12 });
    render(AdminLeaderboardsPage);
    await screen.findByText("global");

    await fireEvent.click(screen.getByRole("button", { name: /perbarui papan global/i }));
    // The refresh is gated behind a confirmation modal.
    expect(screen.getByText("Materialisasi Ulang Snapshot")).toBeTruthy();
    expect(post).not.toHaveBeenCalled();

    const confirm = document.querySelector('[data-role="confirm-refresh"]') as HTMLButtonElement;
    await fireEvent.click(confirm);
    await waitFor(() =>
      expect(post).toHaveBeenCalledWith("/rankings/leaderboards/refresh?scope=global"),
    );
    expect(await screen.findByText(/12 entri/)).toBeTruthy();
  });

  it("disables room/quest refresh until an id is entered", async () => {
    render(AdminLeaderboardsPage);
    await screen.findByText("global");
    const roomBtn = screen.getByRole("button", { name: /perbarui ruang/i });
    expect(roomBtn).toBeDisabled();

    const input = screen.getByPlaceholderText("uuid");
    await fireEvent.input(input, { target: { value: "room-123" } });
    expect(roomBtn).not.toBeDisabled();
  });

  it("renders snapshot metrics", async () => {
    get.mockResolvedValue([
      {
        id: "lb1",
        scope: "global",
        scope_id: null,
        period: "all",
        is_materialized: true,
        updated_at: "2026-01-01T00:00:00Z",
      },
      {
        id: "lb2",
        scope: "room",
        scope_id: "r1",
        period: "all",
        is_materialized: true,
        updated_at: "2026-01-01T00:00:00Z",
      },
      {
        id: "lb3",
        scope: "quest",
        scope_id: "q1",
        period: "all",
        is_materialized: false,
        updated_at: "2026-01-01T00:00:00Z",
      },
    ]);
    render(AdminLeaderboardsPage);
    await waitFor(() =>
      expect(document.querySelector('[data-role="snapshot-count"]')?.textContent?.trim()).toBe("3"),
    );
  });

  it("filters snapshots by scope", async () => {
    get.mockResolvedValue([
      {
        id: "lb1",
        scope: "global",
        scope_id: null,
        period: "all",
        is_materialized: true,
        updated_at: "2026-01-01T00:00:00Z",
      },
      {
        id: "lb2",
        scope: "room",
        scope_id: "r1",
        period: "all",
        is_materialized: true,
        updated_at: "2026-01-01T00:00:00Z",
      },
    ]);
    render(AdminLeaderboardsPage);
    await waitFor(() => expect(document.querySelectorAll("tbody tr").length).toBe(2));

    const select = screen.getByLabelText("Filter cakupan") as HTMLSelectElement;
    await fireEvent.change(select, { target: { value: "room" } });
    await waitFor(() => expect(document.querySelectorAll("tbody tr").length).toBe(1));
  });
});
