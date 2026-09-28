// @vitest-environment jsdom
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, fireEvent, cleanup, waitFor } from "@testing-library/svelte";

vi.mock("$app/navigation", () => ({ goto: vi.fn() }));

const get = vi.fn();
const getPaged = vi.fn();
const post = vi.fn();
vi.mock("../src/lib/api/client", () => ({
  API_BASE: "http://localhost:8000",
  ApiError: class ApiError extends Error {
    status = 0;
  },
  apiGetPaged: (...a: unknown[]) => getPaged(...a),
  api: {
    get: (...a: unknown[]) => get(...a),
    post: (...a: unknown[]) => post(...a),
    put: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
}));

import AdminNotifications from "$routes-panel/admin/notifications/+page.svelte";
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

describe("admin broadcast notifications — preview, count, picker, confirm", () => {
  beforeEach(() => {
    cleanup();
    get.mockReset();
    getPaged.mockReset();
    post.mockReset();
    auth.setUser(admin);
    getPaged.mockResolvedValue({ data: [], total: 42 });
    get.mockResolvedValue([user()]);
    post.mockResolvedValue({ message: "Sent to 42 users" });
  });
  afterEach(() => auth.setUser(null));

  it("shows the active-recipient count and a live preview", async () => {
    render(AdminNotifications);
    await waitFor(() => expect(document.body.textContent).toContain("Semua Pengguna Aktif (42)"));

    const title = screen.getByLabelText(/Judul Notifikasi/);
    await fireEvent.input(title, { target: { value: "Pemeliharaan" } });
    await waitFor(() => expect(screen.getAllByText("Pemeliharaan").length).toBeGreaterThan(0));
  });

  it("confirms before sending the broadcast", async () => {
    render(AdminNotifications);
    await fireEvent.input(screen.getByLabelText(/Judul Notifikasi/), {
      target: { value: "Pengumuman" },
    });
    const submit = screen.getByRole("button", {
      name: /Kirim Siaran Notifikasi/,
    }) as HTMLButtonElement;
    await waitFor(() => expect(submit.disabled).toBe(false));
    await fireEvent.click(submit);

    expect(document.querySelector('[data-role="confirm-broadcast"]')).toBeTruthy();
    expect(post).not.toHaveBeenCalled();

    const confirm = document.querySelector('[data-role="confirm-broadcast"]') as HTMLButtonElement;
    await fireEvent.click(confirm);
    await waitFor(() =>
      expect(post).toHaveBeenCalledWith(
        "/admin/notifications",
        expect.objectContaining({ title: "Pengumuman", user_ids: null }),
      ),
    );
  });

  it("lets an admin pick specific recipients by search", async () => {
    render(AdminNotifications);
    await fireEvent.click(screen.getByLabelText("Penerima Spesifik"));

    // Type a query → search returns a user → add it.
    await fireEvent.input(screen.getByLabelText(/Cari penerima/), { target: { value: "zoe" } });
    await waitFor(() =>
      expect(get.mock.calls.some((c) => String(c[0]).includes("/admin/users?q=zoe"))).toBe(true),
    );
    const addBtn = await screen.findByRole("button", { name: /Zoe/ });
    await fireEvent.click(addBtn);
    // The selected recipient chip appears.
    await waitFor(() => expect(screen.getByText(/Dikirim ke 1 penerima/)).toBeTruthy());
  });

  it("reports a failed recipient search and an unknown audience size", async () => {
    getPaged.mockRejectedValueOnce(new Error("boom"));
    get.mockRejectedValueOnce(new Error("boom"));
    render(AdminNotifications);

    await waitFor(() => expect(document.body.textContent).toContain("jumlah tidak diketahui"));

    await fireEvent.click(screen.getByLabelText("Penerima Spesifik"));
    await fireEvent.input(screen.getByLabelText(/Cari penerima/), { target: { value: "zoe" } });
    expect(await screen.findByText(/Pencarian penerima gagal/)).toBeTruthy();
  });
});
