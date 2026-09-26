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

import AdminAudit from "$routes-panel/admin/audit/+page.svelte";
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

const logs = [
  {
    id: "l1",
    actor_id: "u1aaaaaa",
    action: "auth.login",
    entity_type: "user",
    entity_id: "u1aaaaaa",
    request_id: "req1",
    data: { ip: "127.0.0.1" },
    created_at: "2026-01-01T00:00:00Z",
  },
  {
    id: "l2",
    actor_id: null,
    action: "ledger.reconcile",
    entity_type: "ledger",
    entity_id: null,
    request_id: "req2",
    data: null,
    created_at: "2026-01-02T00:00:00Z",
  },
];

describe("admin audit — free-text search and expandable data", () => {
  beforeEach(() => {
    cleanup();
    get.mockReset();
    auth.setUser(admin);
    get.mockImplementation((path: string) =>
      path.startsWith("/admin/audit-logs") ? Promise.resolve(logs) : Promise.resolve([]),
    );
  });
  afterEach(() => auth.setUser(null));

  it("sends the free-text search to the server on apply", async () => {
    render(AdminAudit);
    await waitFor(() => expect(screen.getByText("auth.login")).toBeTruthy());

    const input = screen.getByLabelText("Cari audit") as HTMLInputElement;
    await fireEvent.input(input, { target: { value: "login" } });
    await fireEvent.click(screen.getByRole("button", { name: "Terapkan" }));
    await waitFor(() =>
      expect(get.mock.calls.some((c) => String(c[0]).includes("q=login"))).toBe(true),
    );
  });

  it("labels system events (no actor)", async () => {
    render(AdminAudit);
    await waitFor(() => expect(screen.getByText("ledger.reconcile")).toBeTruthy());
    await waitFor(() => expect(document.body.textContent).toContain("system"));
  });

  it("expands a data cell on click", async () => {
    render(AdminAudit);
    await waitFor(() => expect(screen.getByText("auth.login")).toBeTruthy());

    const dataBtn = await screen.findByRole("button", { name: "Lihat data" });
    await fireEvent.click(dataBtn);
    await waitFor(() => expect(document.body.textContent).toContain('"ip":"127.0.0.1"'));
  });
});
