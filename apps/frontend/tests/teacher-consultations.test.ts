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

import TeacherConsultations from "$routes-panel/teacher/consultations/+page.svelte";
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

function consult(over: Record<string, unknown> = {}) {
  return {
    id: "c1",
    counselor: "Bu Rina",
    student_name: "Andi",
    topic: "Jurusan kuliah",
    status: "pending",
    scheduled_at: null,
    notes: null,
    created_at: "2026-01-01T00:00:00Z",
    ...over,
  };
}

const consultations = [
  consult({ id: "c1", student_name: "Andi", topic: "Jurusan kuliah", status: "pending" }),
  consult({ id: "c2", student_name: "Bunga", topic: "Strategi belajar", status: "accepted" }),
  consult({ id: "c3", student_name: "Cinta", topic: "Beasiswa", status: "completed" }),
];

describe("teacher consultations — metrics, status tabs, and search", () => {
  beforeEach(() => {
    cleanup();
    get.mockReset();
    post.mockReset();
    auth.setUser(teacher);
    get.mockImplementation((path: string) => {
      if (path.startsWith("/career/consultations/managed")) return Promise.resolve(consultations);
      return Promise.resolve([]);
    });
    post.mockResolvedValue({});
  });
  afterEach(() => auth.setUser(null));

  it("renders the status metrics", async () => {
    render(TeacherConsultations);
    await waitFor(() => expect(screen.getByText("Jurusan kuliah")).toBeTruthy());
    expect(document.querySelector('[data-role="pending-count"]')?.textContent?.trim()).toBe("1");
    expect(document.querySelector('[data-role="total-count"]')?.textContent?.trim()).toBe("3");
  });

  it("filters by status via the tab row (server-side)", async () => {
    render(TeacherConsultations);
    await waitFor(() => expect(screen.getByText("Jurusan kuliah")).toBeTruthy());

    await fireEvent.click(screen.getByRole("tab", { name: "Selesai" }));
    await waitFor(() =>
      expect(get.mock.calls.some((c) => String(c[0]).includes("status=completed"))).toBe(true),
    );
  });

  it("searches by student name", async () => {
    render(TeacherConsultations);
    await waitFor(() => expect(screen.getByText("Jurusan kuliah")).toBeTruthy());

    const input = screen.getByLabelText("Cari konsultasi") as HTMLInputElement;
    await fireEvent.input(input, { target: { value: "bunga" } });
    await waitFor(() => expect(screen.queryByText("Jurusan kuliah")).toBeNull());
    expect(screen.getByText("Strategi belajar")).toBeTruthy();
  });

  it("accepts a pending consultation", async () => {
    render(TeacherConsultations);
    await waitFor(() => expect(screen.getByText("Jurusan kuliah")).toBeTruthy());

    const acceptButtons = screen.getAllByRole("button", { name: "Terima" });
    await fireEvent.click(acceptButtons[0]);
    await waitFor(() => expect(post).toHaveBeenCalledWith("/career/consultations/c1/accept"));
  });
});
