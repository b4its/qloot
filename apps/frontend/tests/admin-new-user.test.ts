// @vitest-environment jsdom
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, fireEvent, cleanup, waitFor } from "@testing-library/svelte";

const goto = vi.fn();
vi.mock("$app/navigation", () => ({ goto: (...a: unknown[]) => goto(...a) }));

const post = vi.fn();
vi.mock("../src/lib/api/client", () => ({
  API_BASE: "http://localhost:8000",
  ApiError: class ApiError extends Error {
    status = 0;
  },
  api: {
    get: vi.fn(),
    post: (...a: unknown[]) => post(...a),
    put: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
}));

import NewUserPage from "$routes-panel/admin/users/new/+page.svelte";
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

describe("admin new-user form — validation, class targeting, and submit", () => {
  beforeEach(() => {
    cleanup();
    post.mockReset();
    goto.mockReset();
    auth.setUser(admin);
    post.mockResolvedValue({ id: "u1", email: "new@x.com" });
  });
  afterEach(() => auth.setUser(null));

  it("keeps submit disabled until required fields are valid", async () => {
    render(NewUserPage);
    const submit = screen.getByRole("button", { name: /Buat akun/i }) as HTMLButtonElement;
    expect(submit.disabled).toBe(true);

    await fireEvent.input(screen.getByPlaceholderText("nama@qloot.example"), {
      target: { value: "not-an-email" },
    });
    // Invalid email → still disabled and an inline hint appears.
    expect(screen.getByText("Format email belum benar.")).toBeTruthy();
    expect(submit.disabled).toBe(true);
  });

  it("shows class fields only for the student role", async () => {
    render(NewUserPage);
    // Default role is student → class fields present.
    expect(screen.getByText("Kode kelas (opsional)")).toBeTruthy();

    const roleSelect = screen.getAllByRole("combobox")[0] as HTMLSelectElement;
    await fireEvent.change(roleSelect, { target: { value: "teacher" } });
    await waitFor(() => expect(screen.queryByText("Kode kelas (opsional)")).toBeNull());
    expect(screen.getByText(/tidak memerlukan penargetan kelas/)).toBeTruthy();
  });

  it("shows a password strength meter", async () => {
    render(NewUserPage);
    await fireEvent.input(screen.getByPlaceholderText("min. 8 karakter"), {
      target: { value: "Abcdef1!" },
    });
    await waitFor(() =>
      expect(document.querySelector('[data-role="password-strength"]')).toBeTruthy(),
    );
  });

  it("posts the payload and redirects on a valid submit", async () => {
    render(NewUserPage);
    await fireEvent.input(screen.getByPlaceholderText("nama@qloot.example"), {
      target: { value: "new@x.com" },
    });
    await fireEvent.input(screen.getByPlaceholderText("Nama lengkap"), {
      target: { value: "New User" },
    });
    await fireEvent.input(screen.getByPlaceholderText("min. 8 karakter"), {
      target: { value: "Password123!" },
    });

    const submit = screen.getByRole("button", { name: /Buat akun/i }) as HTMLButtonElement;
    await waitFor(() => expect(submit.disabled).toBe(false));
    await fireEvent.click(submit);

    await waitFor(() =>
      expect(post).toHaveBeenCalledWith(
        "/admin/users",
        expect.objectContaining({ email: "new@x.com", role: "student" }),
      ),
    );
    await waitFor(() => expect(goto).toHaveBeenCalledWith("/admin/users"));
  });
});
