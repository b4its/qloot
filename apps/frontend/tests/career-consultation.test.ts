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

import ConsultationPage from "$routes-site/career/consultation/+page.svelte";
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

function consult(over: Record<string, unknown> = {}) {
  return {
    id: "c1",
    counselor: "Bu Rina",
    topic: "Jurusan kuliah",
    status: "pending",
    scheduled_at: null,
    notes: null,
    created_at: "2026-01-01T00:00:00Z",
    ...over,
  };
}

const consultations = [
  consult({ id: "c1", topic: "Jurusan kuliah", status: "pending" }),
  consult({ id: "c2", topic: "Strategi belajar", status: "completed" }),
];

describe("career consultation — metrics, status filter, and cancel confirmation", () => {
  beforeEach(() => {
    cleanup();
    get.mockReset();
    post.mockReset();
    auth.setUser(student);
    get.mockImplementation((path: string) => {
      if (path.startsWith("/career/consultations")) return Promise.resolve(consultations);
      if (path.startsWith("/career/counselors"))
        return Promise.resolve([{ user_id: "g1", name: "Bu Rina", role: "Guru BK" }]);
      return Promise.resolve([]);
    });
    post.mockResolvedValue({});
  });
  afterEach(() => auth.setUser(null));

  it("renders the status metrics", async () => {
    render(ConsultationPage);
    await waitFor(() => expect(screen.getByText("Jurusan kuliah")).toBeTruthy());
    expect(document.querySelector('[data-role="pending-count"]')?.textContent?.trim()).toBe("1");
  });

  it("filters by status", async () => {
    render(ConsultationPage);
    await waitFor(() => expect(screen.getByText("Jurusan kuliah")).toBeTruthy());

    await fireEvent.click(screen.getByRole("tab", { name: "Selesai" }));
    await waitFor(() => expect(screen.queryByText("Jurusan kuliah")).toBeNull());
    expect(screen.getByText("Strategi belajar")).toBeTruthy();
  });

  it("confirms before cancelling a pending session", async () => {
    render(ConsultationPage);
    await waitFor(() => expect(screen.getByText("Jurusan kuliah")).toBeTruthy());

    await fireEvent.click(screen.getByRole("button", { name: "Batal" }));
    expect(screen.getByText("Batalkan Sesi Konseling")).toBeTruthy();
    expect(post).not.toHaveBeenCalled();

    const confirm = document.querySelector(
      '[data-role="confirm-cancel-consultation"]',
    ) as HTMLButtonElement;
    await fireEvent.click(confirm);
    await waitFor(() => expect(post).toHaveBeenCalledWith("/career/consultations/c1/cancel"));
  });
});
