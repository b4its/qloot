// @vitest-environment jsdom
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, cleanup, fireEvent, waitFor } from "@testing-library/svelte";

vi.mock("$app/stores", () => ({
  page: {
    subscribe: (fn: (v: unknown) => void) => (
      fn({
        params: { courseId: "c-101", lessonId: "l-1" },
        url: new URL("http://localhost:3000/learning/c-101"),
      }),
      () => {}
    ),
  },
}));

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
  },
}));

import CoursePage from "../src/routes/(site)/learning/[courseId]/+page.svelte";
import LessonPage from "../src/routes/(site)/learning/[courseId]/lesson/[lessonId]/+page.svelte";

const mockCourse = {
  id: "c-101",
  title: "Dasar Pemrograman Web Modern",
  description: "Pelajari HTML, CSS, JavaScript, dan framework reaktif.",
};

const mockLessons = [
  {
    id: "l-1",
    course_id: "c-101",
    title: "Pengenalan DOM dan Browser API",
    video_url: "https://example.com/video1.mp4",
    content_md: "Konten penjelasan DOM.",
  },
  {
    id: "l-2",
    course_id: "c-101",
    title: "Asynchronous JavaScript & Fetch",
    video_url: null,
    content_md: "Konten materi async await.",
  },
];

const mockProgress = {
  percent: 50,
  completed_lessons: 1,
  total_lessons: 2,
  next_lesson_id: "l-2",
  next_lesson_title: "Asynchronous JavaScript & Fetch",
};

const mockUserProgress = [
  {
    id: "p-1",
    course_id: "c-101",
    lesson_id: "l-1",
    completed: true,
    progress_percent: 100,
  },
];

describe("course syllabus and lesson UX overhaul", () => {
  beforeEach(() => {
    cleanup();
    get.mockReset();
    post.mockReset();

    get.mockImplementation(async (path: string) => {
      if (path === "/courses/c-101") return mockCourse;
      if (path === "/courses/c-101/lessons") return mockLessons;
      if (path === "/courses/c-101/progress") return mockProgress;
      if (path.startsWith("/me/learning-progress")) return mockUserProgress;
      if (path === "/lessons/l-1") return mockLessons[0];
      if (path === "/lessons/l-1/materials") return [];
      return [];
    });
    post.mockResolvedValue({ id: "p-new", completed: true, progress_percent: 100 });
  });

  afterEach(() => cleanup());

  it("renders course syllabus metrics, filter buttons, search input, and lesson list", async () => {
    render(CoursePage);
    expect(await screen.findByText("Dasar Pemrograman Web Modern")).toBeTruthy();

    // Check summary metrics
    expect(screen.getByText("Total Materi")).toBeTruthy();
    expect(screen.getByText("Materi Selesai")).toBeTruthy();
    expect(screen.getByText("Kelulusan")).toBeTruthy();
    expect(screen.getByText("50%")).toBeTruthy();

    // Check filter buttons
    expect(screen.getByRole("button", { name: "Semua (2)" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Selesai (1)" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Belum (1)" })).toBeTruthy();

    // Check lesson cards
    expect(screen.getByRole("link", { name: "Pengenalan DOM dan Browser API" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "Asynchronous JavaScript & Fetch" })).toBeTruthy();
  });

  it("filters lessons by search query and completion filter", async () => {
    render(CoursePage);
    expect(await screen.findByText("Dasar Pemrograman Web Modern")).toBeTruthy();

    // Search query filter
    const searchInput = screen.getByPlaceholderText("Cari materi...");
    await fireEvent.input(searchInput, { target: { value: "Async" } });

    expect(screen.queryByRole("link", { name: "Pengenalan DOM dan Browser API" })).toBeNull();
    expect(screen.getByRole("link", { name: "Asynchronous JavaScript & Fetch" })).toBeTruthy();

    // Reset search
    await fireEvent.input(searchInput, { target: { value: "" } });
    expect(screen.getByRole("link", { name: "Pengenalan DOM dan Browser API" })).toBeTruthy();

    // Filter by completed
    const completedTab = screen.getByRole("button", { name: "Selesai (1)" });
    await fireEvent.click(completedTab);
    expect(screen.getByRole("link", { name: "Pengenalan DOM dan Browser API" })).toBeTruthy();
    expect(screen.queryByRole("link", { name: "Asynchronous JavaScript & Fetch" })).toBeNull();
  });

  it("toggles lesson completion on course page", async () => {
    render(CoursePage);
    expect(await screen.findByText("Dasar Pemrograman Web Modern")).toBeTruthy();

    const toggleBtns = screen.getAllByRole("button", { name: /Tandai Selesai|Batal Selesai/ });
    expect(toggleBtns.length).toBe(2);

    await fireEvent.click(toggleBtns[1]); // Toggle uncompleted lesson l-2
    expect(post).toHaveBeenCalledWith("/lessons/l-2/progress", {
      progress_percent: 100,
      completed: true,
    });
  });

  it("renders lesson detail with course sequence, previous/next buttons, and completion toggle", async () => {
    render(LessonPage);
    expect(await screen.findByText("Pengenalan DOM dan Browser API")).toBeTruthy();

    // Sequence badge
    expect(screen.getByText("Materi 1 dari 2")).toBeTruthy();

    // Sibling navigation
    expect(screen.getByText("Ini adalah materi pertama")).toBeTruthy();
    expect(screen.getByText("Asynchronous JavaScript & Fetch")).toBeTruthy();

    // Toggle complete
    const toggleBtn = screen.getByRole("button", { name: /Batal Tandai Selesai/ });
    await fireEvent.click(toggleBtn);

    await waitFor(() => {
      expect(post).toHaveBeenCalledWith("/lessons/l-1/progress", {
        progress_percent: 0,
        completed: false,
      });
    });
  });
});
