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

import ProfilePage from "$routes-site/profile/+page.svelte";
import { auth } from "../src/lib/stores/auth";

const student = {
  id: "u1",
  email: "s@x.com",
  full_name: "Student",
  is_active: true,
  chain_user_ref: "0x0",
  created_at: "2026-01-01T00:00:00Z",
  roles: ["student"],
};

describe("profile — privacy data export (W5)", () => {
  beforeEach(() => {
    cleanup();
    get.mockReset();
    auth.setUser(student);
    get.mockImplementation((path: string) => {
      if (path === "/auth/sessions") return Promise.resolve([]);
      if (path === "/gamification/me") return Promise.resolve(null);
      return Promise.resolve({ followers: 0, following: 0 });
    });
  });
  afterEach(() => auth.setUser(null));

  it("renders a privacy section explaining data portability and retention", async () => {
    render(ProfilePage);
    await waitFor(() => expect(document.querySelector('[data-role="privacy-data"]')).toBeTruthy());
    expect(screen.getByText(/Privasi & data/i)).toBeTruthy();
    expect(screen.getByText(/format JSON/i)).toBeTruthy();
    expect(screen.getByText(/retensi/i)).toBeTruthy();
  });

  it("downloads the export from the self-service endpoint", async () => {
    const blob = new Blob(["{}"], { type: "application/json" });
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, blob: () => Promise.resolve(blob) });
    vi.stubGlobal("fetch", fetchMock);
    const createObjectURL = vi.fn(() => "blob:mock");
    const revokeObjectURL = vi.fn();
    vi.stubGlobal("URL", { ...URL, createObjectURL, revokeObjectURL });

    render(ProfilePage);
    await waitFor(() => expect(document.querySelector('[data-role="export-data"]')).toBeTruthy());
    await fireEvent.click(document.querySelector('[data-role="export-data"]') as HTMLButtonElement);

    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        "http://localhost:8000/api/v1/auth/export",
        expect.objectContaining({ credentials: "include" }),
      ),
    );
    expect(createObjectURL).toHaveBeenCalled();
    vi.unstubAllGlobals();
  });
});
