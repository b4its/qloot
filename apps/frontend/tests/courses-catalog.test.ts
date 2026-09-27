// @vitest-environment jsdom
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, fireEvent, cleanup, waitFor } from "@testing-library/svelte";

vi.mock("$app/stores", () => ({
  page: {
    subscribe: (fn: (v: unknown) => void) => (
      fn({ params: {}, url: new URL("http://x/courses") }),
      () => {}
    ),
  },
}));

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

import CoursesPage from "$routes-site/courses/+page.svelte";
import { auth } from "../src/lib/stores/auth";

const courses = [
  {
    id: "c1",
    title: "Fisika Dasar",
    slug: "fisika-dasar",
    owner_id: "t1",
    owner_name: "Bu Ani",
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
    title: "Matematika Lanjut",
    slug: "matematika-lanjut",
    owner_id: "t1",
    owner_name: "Pak Budi",
    is_published: true,
    subject: "Matematika",
    class_code: "1A",
    class_type: "IPA",
    lesson_count: 2,
    created_at: "2026-01-02T00:00:00Z",
    updated_at: "2026-01-02T00:00:00Z",
  },
];

const progress = [
  {
    id: "p1",
    lesson_id: "l1",
    course_id: "c1",
    progress_percent: 100,
    completed: true,
    completed_at: "2026-01-03T00:00:00Z",
  },
  {
    id: "p2",
    lesson_id: "l2",
    course_id: "c1",
    progress_percent: 100,
    completed: true,
    completed_at: "2026-01-03T00:00:00Z",
  },
  // c2 fully complete (2/2).
  {
    id: "p3",
    lesson_id: "l3",
    course_id: "c2",
    progress_percent: 100,
    completed: true,
    completed_at: "2026-01-03T00:00:00Z",
  },
  {
    id: "p4",
    lesson_id: "l4",
    course_id: "c2",
    progress_percent: 100,
    completed: true,
    completed_at: "2026-01-03T00:00:00Z",
  },
];

describe("courses catalog — progress-aware", () => {
  beforeEach(() => {
    cleanup();
    get.mockReset();
    auth.setUser({
      id: "u1",
      email: "s@x.com",
      full_name: "Student",
      is_active: true,
      chain_user_ref: "0x0",
      created_at: "2026-01-01T00:00:00Z",
      roles: ["student"],
      class_code: "1A",
      class_type: "IPA",
    });
    get.mockImplementation((path: string) => {
      if (path.startsWith("/me/learning-progress")) return Promise.resolve(progress);
      if (path.startsWith("/courses")) return Promise.resolve(courses);
      return Promise.resolve([]);
    });
  });
  afterEach(() => auth.setUser(null));

  it("shows per-course progress and the overall completion metric", async () => {
    render(CoursesPage);
    await waitFor(() => expect(screen.getByText("Fisika Dasar")).toBeTruthy());
    // c1 = 2/4 done, c2 = 2/2 done → 4 of 6 lessons = 67%.
    expect(screen.getByText("2/4")).toBeTruthy();
    expect(screen.getByText("2/2")).toBeTruthy();
    expect(document.querySelector('[data-role="overall-pct"]')?.textContent?.trim()).toBe("67%");
  });

  it("marks fully-completed courses as tuntas", async () => {
    render(CoursesPage);
    await waitFor(() => expect(screen.getByText("Matematika Lanjut")).toBeTruthy());
    expect(screen.getByText("Tuntas")).toBeTruthy();
  });

  it("filters by subject", async () => {
    render(CoursesPage);
    await waitFor(() => expect(screen.getByText("Fisika Dasar")).toBeTruthy());

    const select = screen.getByLabelText("Filter mata pelajaran") as HTMLSelectElement;
    await fireEvent.change(select, { target: { value: "Matematika" } });
    await waitFor(() => expect(screen.queryByText("Fisika Dasar")).toBeNull());
    expect(screen.getByText("Matematika Lanjut")).toBeTruthy();
  });

  it("sorts by highest progress", async () => {
    render(CoursesPage);
    await waitFor(() => expect(screen.getByText("Fisika Dasar")).toBeTruthy());

    const select = screen.getByLabelText("Urutkan") as HTMLSelectElement;
    await fireEvent.change(select, { target: { value: "progress" } });
    // c2 (100%) sorts before c1 (50%).
    await waitFor(() => {
      const headings = screen.getAllByRole("heading", { level: 2 }).map((h) => h.textContent);
      expect(headings.indexOf("Matematika Lanjut")).toBeLessThan(headings.indexOf("Fisika Dasar"));
    });
  });

  it("shows a login preview without calling protected APIs for anonymous visitors", async () => {
    auth.setUser(null);
    get.mockReset();

    render(CoursesPage);

    expect(
      await screen.findByRole("heading", { name: "Pelajaran disesuaikan dengan kelasmu" }),
    ).toBeTruthy();
    expect(screen.getByRole("link", { name: /masuk untuk melihat katalog/i })).toHaveAttribute(
      "href",
      "/login?next=%2Fcourses",
    );
    expect(get).not.toHaveBeenCalled();
  });
});
