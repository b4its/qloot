// @vitest-environment jsdom
import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, cleanup, waitFor, fireEvent, screen } from "@testing-library/svelte";

const get = vi.fn();
const put = vi.fn();
const del = vi.fn();
vi.mock("../src/lib/api/client", () => ({
  API_BASE: "http://localhost:8000",
  ApiError: class ApiError extends Error {
    status = 0;
  },
  api: {
    get: (...a: unknown[]) => get(...a),
    post: vi.fn(),
    put: (...a: unknown[]) => put(...a),
    patch: vi.fn(),
    delete: (...a: unknown[]) => del(...a),
  },
}));

import DashboardPage from "$routes-site/dashboard/+page.svelte";
import { auth } from "../src/lib/stores/auth";

const grades = [
  { id: "g1", subject: "Matematika", grade: 80, term: "2025/2026-genap" },
  { id: "g2", subject: "Fisika", grade: 75, term: "2025/2026-genap" },
];

describe("dashboard inline grade editing (no native prompt)", () => {
  beforeEach(() => {
    cleanup();
    get.mockReset();
    put.mockReset();
    del.mockReset();
    auth.setUser({
      id: "u1",
      email: "s@x.com",
      full_name: "Student",
      is_active: true,
      chain_user_ref: "0x0",
      created_at: "2026-01-01T00:00:00Z",
      roles: ["student"],
    });
    get.mockImplementation((path: string) => {
      if (path === "/career/grades") return Promise.resolve(grades);
      if (path === "/career/dashboard") return Promise.resolve(null);
      return Promise.resolve([]);
    });
  });

  it("edits a grade inline and saves via PUT without window.prompt", async () => {
    put.mockResolvedValue({});
    render(DashboardPage);
    await waitFor(() => expect(screen.getByLabelText("Ubah nilai Matematika")).toBeTruthy());

    await fireEvent.click(screen.getByLabelText("Ubah nilai Matematika"));
    const input = (await screen.findByLabelText("Nilai baru Matematika")) as HTMLInputElement;
    expect(input.value).toBe("80");

    await fireEvent.input(input, { target: { value: "90" } });
    await fireEvent.click(screen.getByLabelText("Simpan nilai Matematika"));

    await waitFor(() => expect(put).toHaveBeenCalledWith("/career/grades/g1", { grade: 90 }));
  });

  it("deletes a grade through the themed confirm dialog", async () => {
    del.mockResolvedValue({});
    render(DashboardPage);
    await waitFor(() => expect(screen.getByLabelText("Hapus nilai Fisika")).toBeTruthy());

    await fireEvent.click(screen.getByLabelText("Hapus nilai Fisika"));
    const confirm = document.querySelector('[data-role="confirm-action"]') as HTMLButtonElement;
    expect(confirm).toBeTruthy();
    await fireEvent.click(confirm);

    await waitFor(() => expect(del).toHaveBeenCalledWith("/career/grades/g2"));
  });
});
