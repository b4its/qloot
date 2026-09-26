// @vitest-environment jsdom
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, fireEvent, cleanup, waitFor } from "@testing-library/svelte";

vi.mock("$app/navigation", () => ({ goto: vi.fn() }));

const getPaged = vi.fn();
vi.mock("../src/lib/api/client", () => ({
  API_BASE: "http://localhost:8000",
  ApiError: class ApiError extends Error {
    status = 0;
  },
  apiGetPaged: (...a: unknown[]) => getPaged(...a),
  api: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
}));

import AdminUsers from "$routes-panel/admin/users/+page.svelte";
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

function user(over: Record<string, unknown> = {}) {
  return {
    id: "u1",
    email: "zoe@x.com",
    full_name: "Zoe",
    is_active: true,
    chain_user_ref: "0x0",
    created_at: "2026-01-01T00:00:00Z",
    roles: ["student"],
    ...over,
  };
}

describe("admin users — server-side search and filters", () => {
  beforeEach(() => {
    cleanup();
    getPaged.mockReset();
    auth.setUser(admin);
    getPaged.mockResolvedValue({ data: [user()], total: 1 });
  });
  afterEach(() => auth.setUser(null));

  it("sends the search term to the server (debounced)", async () => {
    render(AdminUsers);
    await waitFor(() => expect(screen.getByText("zoe@x.com")).toBeTruthy());

    const input = screen.getByLabelText("Cari pengguna") as HTMLInputElement;
    await fireEvent.input(input, { target: { value: "zoe" } });
    await waitFor(() =>
      expect(getPaged.mock.calls.some((c) => String(c[0]).includes("q=zoe"))).toBe(true),
    );
  });

  it("sends the role filter to the server", async () => {
    render(AdminUsers);
    await waitFor(() => expect(screen.getByText("zoe@x.com")).toBeTruthy());

    const select = screen.getByLabelText("Filter peran") as HTMLSelectElement;
    await fireEvent.change(select, { target: { value: "teacher" } });
    await waitFor(() =>
      expect(getPaged.mock.calls.some((c) => String(c[0]).includes("role=teacher"))).toBe(true),
    );
  });

  it("sends the active/inactive status filter to the server", async () => {
    render(AdminUsers);
    await waitFor(() => expect(screen.getByText("zoe@x.com")).toBeTruthy());

    await fireEvent.click(screen.getByRole("button", { name: "Nonaktif" }));
    await waitFor(() =>
      expect(getPaged.mock.calls.some((c) => String(c[0]).includes("is_active=false"))).toBe(true),
    );
  });

  it("shows the filtered total from the response", async () => {
    getPaged.mockResolvedValue({ data: [user()], total: 42 });
    render(AdminUsers);
    await waitFor(() =>
      expect(document.querySelector('[data-role="filtered-total"]')?.textContent?.trim()).toBe(
        "42 pengguna",
      ),
    );
  });
});
