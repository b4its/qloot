// @vitest-environment jsdom
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, fireEvent, cleanup, waitFor } from "@testing-library/svelte";

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

import PathsPage from "$routes-site/paths/+page.svelte";

const courses = [
  {
    id: "c1",
    title: "Fisika Dasar",
    slug: "fisika-dasar",
    owner_id: "t1",
    is_published: true,
    subject: "Fisika",
    class_code: "1A",
    class_type: "IPA",
    lesson_count: 4,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  },
  {
    id: "c2",
    title: "Fisika Lanjut",
    slug: "fisika-lanjut",
    owner_id: "t1",
    is_published: true,
    subject: "Fisika",
    class_code: "2A",
    class_type: "IPA",
    lesson_count: 3,
    created_at: "2026-01-02T00:00:00Z",
    updated_at: "2026-01-02T00:00:00Z",
  },
  {
    id: "c3",
    title: "Matematika",
    slug: "matematika",
    owner_id: "t1",
    is_published: true,
    subject: "Matematika",
    class_code: "1A",
    class_type: "IPA",
    lesson_count: 5,
    created_at: "2026-01-03T00:00:00Z",
    updated_at: "2026-01-03T00:00:00Z",
  },
];

describe("paths (mata pelajaran) — search and class filter", () => {
  beforeEach(() => {
    cleanup();
    get.mockReset();
    get.mockImplementation((path: string) =>
      path.startsWith("/courses") ? Promise.resolve(courses) : Promise.resolve([]),
    );
    // jsdom lacks a proper <select> change bubbling; use fireEvent.change below.
  });
  afterEach(() => cleanup());

  it("renders overview metrics for subjects, courses, and classes", async () => {
    render(PathsPage);
    await waitFor(() => expect(screen.getByText("Fisika")).toBeTruthy());
    // 2 subjects (Fisika, Matematika), 3 courses total, 2 classes (1A, 2A).
    expect(document.querySelector('[data-role="total-lessons"]')?.textContent?.trim()).toBe("3");
    expect(document.querySelector('[data-role="total-classes"]')?.textContent?.trim()).toBe("2");
  });

  it("filters subjects by class", async () => {
    render(PathsPage);
    await waitFor(() => expect(screen.getByText("Fisika")).toBeTruthy());

    const select = screen.getByLabelText("Filter kelas") as HTMLSelectElement;
    await fireEvent.change(select, { target: { value: "2A" } });
    await waitFor(() => expect(screen.queryByText("Matematika")).toBeNull());
    expect(screen.getByText("Fisika")).toBeTruthy();
  });

  it("searches subjects by name", async () => {
    render(PathsPage);
    await waitFor(() => expect(screen.getByText("Fisika")).toBeTruthy());

    const input = screen.getByLabelText("Cari mata pelajaran") as HTMLInputElement;
    await fireEvent.input(input, { target: { value: "matematika" } });
    await waitFor(() => expect(screen.queryByText("Fisika")).toBeNull());
    expect(screen.getByText("Matematika")).toBeTruthy();
  });
});
