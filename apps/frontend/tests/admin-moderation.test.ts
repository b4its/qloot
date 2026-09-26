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

import AdminModeration from "$routes-panel/admin/moderation/+page.svelte";
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

function report(over: Record<string, unknown> = {}) {
  return {
    id: "r1",
    reporter_id: "u1",
    target_type: "post",
    target_id: "p1",
    reason: "spam",
    status: "open",
    body: "beli sekarang",
    created_at: "2026-01-01T00:00:00Z",
    ...over,
  };
}

const reports = [
  report({ id: "r1", reason: "spam", target_type: "post" }),
  report({ id: "r2", reason: "ujaran kebencian", body: "kata kasar", target_type: "comment" }),
];

describe("admin moderation — metrics, search, and destructive confirmation", () => {
  beforeEach(() => {
    cleanup();
    get.mockReset();
    post.mockReset();
    auth.setUser(admin);
    get.mockImplementation((path: string) =>
      path.startsWith("/community/reports") ? Promise.resolve(reports) : Promise.resolve([]),
    );
    post.mockResolvedValue({});
  });
  afterEach(() => auth.setUser(null));

  it("renders the status metrics", async () => {
    render(AdminModeration);
    await waitFor(() =>
      expect(document.querySelector('[data-role="open-count"]')?.textContent?.trim()).toBe("2"),
    );
  });

  it("searches reports by reason", async () => {
    render(AdminModeration);
    await waitFor(() => expect(screen.getByText("spam")).toBeTruthy());

    const input = screen.getByLabelText("Cari laporan") as HTMLInputElement;
    await fireEvent.input(input, { target: { value: "kebencian" } });
    await waitFor(() => expect(screen.queryByText("spam")).toBeNull());
    expect(screen.getByText("ujaran kebencian")).toBeTruthy();
  });

  it("confirms before hiding and calls the moderate endpoint", async () => {
    render(AdminModeration);
    await waitFor(() =>
      expect(screen.getAllByRole("button", { name: "Sembunyikan" }).length).toBe(2),
    );

    await fireEvent.click(screen.getAllByRole("button", { name: "Sembunyikan" })[0]);
    expect(screen.getByText("Sembunyikan Konten")).toBeTruthy();
    expect(post).not.toHaveBeenCalled();

    const confirm = document.querySelector('[data-role="confirm-moderate"]') as HTMLButtonElement;
    await fireEvent.click(confirm);
    await waitFor(() =>
      expect(post).toHaveBeenCalledWith("/community/reports/r1/moderate", { action: "hide" }),
    );
  });

  it("dismisses a report without confirmation", async () => {
    render(AdminModeration);
    await waitFor(() =>
      expect(screen.getAllByRole("button", { name: "Tolak laporan" }).length).toBe(2),
    );

    await fireEvent.click(screen.getAllByRole("button", { name: "Tolak laporan" })[0]);
    await waitFor(() =>
      expect(post).toHaveBeenCalledWith("/community/reports/r1/moderate", { action: "dismiss" }),
    );
  });
});
