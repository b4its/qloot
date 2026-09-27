// @vitest-environment jsdom
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, fireEvent, cleanup, waitFor } from "@testing-library/svelte";

vi.mock("$app/stores", () => ({
  page: {
    subscribe: (fn: (v: unknown) => void) => {
      fn({ params: {}, url: new URL("http://localhost:3000/rooms") });
      return () => {};
    },
  },
}));
vi.mock("$app/navigation", () => ({ goto: vi.fn() }));

const get = vi.fn();
const patch = vi.fn();
vi.mock("../src/lib/api/client", () => ({
  API_BASE: "http://localhost:8000",
  wsUrl: (p: string) => `ws://localhost:8000${p}`,
  ApiError: class ApiError extends Error {
    status = 0;
  },
  api: {
    get: (...a: unknown[]) => get(...a),
    post: vi.fn(),
    put: vi.fn(),
    patch: (...a: unknown[]) => patch(...a),
    delete: vi.fn(),
  },
}));

import RoomsPage from "$routes-site/rooms/+page.svelte";
import { auth } from "../src/lib/stores/auth";

const teacher = {
  id: "t1",
  email: "t@x.com",
  full_name: "Teacher",
  is_active: true,
  chain_user_ref: "0x0",
  created_at: "2026-01-01T00:00:00Z",
  roles: ["teacher"],
};

const room = {
  id: "r-1",
  name: "Ruang Fisika",
  code: "FSK101",
  owner_id: "t1",
  status: "open",
  max_participants: 50,
  is_public: true,
  is_locked: false,
  created_at: "2026-01-01T00:00:00Z",
};

describe("rooms list — inline edit (PATCH /rooms/{id})", () => {
  beforeEach(() => {
    cleanup();
    get.mockReset();
    patch.mockReset();
    auth.setUser(teacher);
    get.mockImplementation((path: string) => {
      if (path.startsWith("/rooms")) return Promise.resolve([room]);
      return Promise.resolve([]);
    });
    patch.mockResolvedValue({ ...room, name: "Ruang Fisika Lanjut" });
  });
  afterEach(() => auth.setUser(null));

  it("opens the edit form from the edit button", async () => {
    render(RoomsPage);
    await waitFor(() => expect(screen.getByText("Ruang Fisika")).toBeTruthy());

    const editBtn = screen.getByRole("button", { name: /Ubah ruang Ruang Fisika/ });
    await fireEvent.click(editBtn);
    // The inline name input appears with the current name.
    expect(await screen.findByDisplayValue("Ruang Fisika")).toBeTruthy();
  });

  it("patches the room and updates the card on save", async () => {
    render(RoomsPage);
    await waitFor(() => expect(screen.getByText("Ruang Fisika")).toBeTruthy());
    await fireEvent.click(screen.getByRole("button", { name: /Ubah ruang Ruang Fisika/ }));

    const nameInput = (await screen.findByDisplayValue("Ruang Fisika")) as HTMLInputElement;
    await fireEvent.input(nameInput, { target: { value: "Ruang Fisika Lanjut" } });
    await fireEvent.click(screen.getByRole("button", { name: "Simpan" }));

    await waitFor(() =>
      expect(patch).toHaveBeenCalledWith(
        "/rooms/r-1",
        expect.objectContaining({ name: "Ruang Fisika Lanjut", is_public: true }),
      ),
    );
    await waitFor(() => expect(screen.getByText("Ruang Fisika Lanjut")).toBeTruthy());
  });
});
