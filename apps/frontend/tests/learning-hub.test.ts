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

import LearningPage from "$routes-site/learning/+page.svelte";
import { auth } from "../src/lib/stores/auth";

const student = {
  id: "u1",
  email: "s@x.com",
  full_name: "Student",
  is_active: true,
  chain_user_ref: "0x0",
  created_at: "2026-01-01T00:00:00Z",
  roles: ["student"],
  class_code: "1A",
  class_type: "IPA",
};

const courses = [
  {
    id: "c1",
    title: "Fisika Dasar",
    slug: "fisika",
    owner_id: "t1",
    is_published: true,
    subject: "Fisika",
    class_code: "1A",
    lesson_count: 4,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  },
  {
    id: "c2",
    title: "Matematika",
    slug: "matematika",
    owner_id: "t1",
    is_published: true,
    subject: "Matematika",
    class_code: "1A",
    lesson_count: 2,
    created_at: "2026-01-02T00:00:00Z",
    updated_at: "2026-01-02T00:00:00Z",
  },
];

const progress = [
  // c1 partially done (1/4) → "started"; c2 fully done (2/2) → "done".
  { id: "p1", lesson_id: "l1", course_id: "c1", progress_percent: 100, completed: true },
  { id: "p2", lesson_id: "l2", course_id: "c2", progress_percent: 100, completed: true },
  { id: "p3", lesson_id: "l3", course_id: "c2", progress_percent: 100, completed: true },
];

describe("learning page — resume, metrics, and filters", () => {
  beforeEach(() => {
    cleanup();
    get.mockReset();
    auth.setUser(student);
    get.mockImplementation((path: string) => {
      if (path.startsWith("/me/learning-progress")) return Promise.resolve(progress);
      if (path.startsWith("/courses")) return Promise.resolve(courses);
      return Promise.resolve([]);
    });
  });
  afterEach(() => auth.setUser(null));

  it("shows a continue-learning banner for the in-progress course", async () => {
    render(LearningPage);
    await waitFor(() => expect(screen.getAllByText("Fisika Dasar").length).toBeGreaterThan(0));
    const resume = document.querySelector('[data-role="resume"]') as HTMLElement;
    expect(resume).toBeTruthy();
    expect(resume.textContent).toContain("Lanjutkan belajar");
    expect(resume.textContent).toContain("Fisika Dasar");
  });

  it("renders completion metrics", async () => {
    render(LearningPage);
    await waitFor(() => expect(screen.getAllByText("Fisika Dasar").length).toBeGreaterThan(0));
    // c2 is fully done → 1 done course; overall 3/6 = 50%.
    expect(document.querySelector('[data-role="done-courses"]')?.textContent?.trim()).toBe("1");
    expect(screen.getByText("50%")).toBeTruthy();
  });

  it("filters to completed courses", async () => {
    render(LearningPage);
    await waitFor(() => expect(screen.getAllByText("Fisika Dasar").length).toBeGreaterThan(0));

    await fireEvent.click(screen.getByRole("button", { name: "Selesai" }));
    // Scope to the course cards (the resume banner is always shown).
    await waitFor(() => expect(document.querySelectorAll("[data-course]").length).toBe(1));
    expect(document.querySelector('[data-course="c2"]')).toBeTruthy();
    expect(document.querySelector('[data-course="c1"]')).toBeNull();
  });

  it("searches courses by title", async () => {
    render(LearningPage);
    await waitFor(() => expect(screen.getAllByText("Fisika Dasar").length).toBeGreaterThan(0));

    const input = screen.getByLabelText("Cari pelajaran") as HTMLInputElement;
    await fireEvent.input(input, { target: { value: "matematika" } });
    await waitFor(() => expect(document.querySelector('[data-course="c1"]')).toBeNull());
    expect(document.querySelector('[data-course="c2"]')).toBeTruthy();
  });
});
