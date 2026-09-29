// @vitest-environment jsdom
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, cleanup, waitFor } from "@testing-library/svelte";

vi.mock("$app/stores", () => ({
  page: {
    subscribe: (fn: (v: unknown) => void) => (
      fn({ params: { id: "c1" }, url: new URL("http://x/courses/c1") }),
      () => {}
    ),
  },
}));
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

import CourseDetailPage from "$routes-site/courses/[id]/+page.svelte";
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

const course = {
  id: "c1",
  title: "Fisika Dasar",
  slug: "fisika",
  owner_id: "t1",
  owner_name: "Bu Ani",
  is_published: true,
  subject: "Fisika",
  class_code: "1A",
  class_type: "IPA",
  description: "d",
  lesson_count: 3,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

const lessons = [
  { id: "l1", course_id: "c1", title: "Materi A", position: 0, is_published: true },
  { id: "l2", course_id: "c1", title: "Materi B", position: 1, is_published: true },
  { id: "l3", course_id: "c1", title: "Materi C", position: 2, is_published: true },
];

const progress = [
  { id: "p1", lesson_id: "l1", course_id: "c1", progress_percent: 100, completed: true },
];

describe("course detail — student progress awareness", () => {
  beforeEach(() => {
    cleanup();
    get.mockReset();
    auth.setUser(student);
    get.mockImplementation((path: string) => {
      if (path.includes("/me/learning-progress")) return Promise.resolve(progress);
      if (path.includes("/lessons")) return Promise.resolve(lessons);
      if (path.startsWith("/courses/")) return Promise.resolve(course);
      if (path.startsWith("/certificates")) return Promise.resolve([]);
      return Promise.resolve([]);
    });
  });
  afterEach(() => auth.setUser(null));

  it("requests progress scoped to the course", async () => {
    render(CourseDetailPage);
    await waitFor(() =>
      expect(get.mock.calls.some((c) => String(c[0]).includes("course_id=c1"))).toBe(true),
    );
  });

  it("shows the completion progress bar and summary", async () => {
    render(CourseDetailPage);
    // 1 of 3 done → 33%.
    await waitFor(() => expect(screen.getByText("1 dari 3 materi selesai· 33%")).toBeTruthy());
    const bar = screen.getByRole("progressbar", { name: "Progres pelajaran" });
    expect(bar.getAttribute("aria-valuenow")).toBe("1");
    expect(bar.getAttribute("aria-valuemax")).toBe("3");
  });

  it("marks completed lessons and the resume pointer", async () => {
    render(CourseDetailPage);
    await waitFor(() => expect(document.querySelector('[data-lesson="l1"]')).toBeTruthy());
    // l1 is completed, l2 is the first unfinished → resume badge.
    expect(document.querySelector('[data-lesson="l1"]')?.getAttribute("data-done")).toBe("true");
    expect(document.querySelector('[data-lesson="l2"]')?.getAttribute("data-done")).toBe("false");
    expect(screen.getByText("Lanjutkan di sini")).toBeTruthy();
  });

  it("warns instead of pretending the course is un-started when progress fails", async () => {
    get.mockImplementation((path: string) => {
      if (path.includes("/me/learning-progress")) return Promise.reject(new Error("boom"));
      if (path.includes("/lessons")) return Promise.resolve(lessons);
      if (path.startsWith("/courses/")) return Promise.resolve(course);
      return Promise.resolve([]);
    });

    render(CourseDetailPage);

    // Course still loads; the failed progress fetch is disclosed.
    await waitFor(() => expect(document.querySelector('[data-lesson="l1"]')).toBeTruthy());
    expect(await screen.findByText(/progres belajarmu belum dapat dimuat/i)).toBeTruthy();
    expect(screen.queryByRole("progressbar", { name: "Progres pelajaran" })).toBeNull();
  });

  it("loads progress once auth resolves after mount (hard refresh)", async () => {
    // Simulate a hard refresh: the page mounts while auth is still loading, so
    // the student is unknown at mount. Progress must still be fetched once
    // auth settles — not left on the 0/N placeholder.
    let resolveMe: (u: unknown) => void = () => {};
    const mePromise = new Promise((res) => {
      resolveMe = res;
    });
    get.mockImplementation((path: string) => {
      if (path.includes("/auth/me")) return mePromise;
      if (path.includes("/me/learning-progress")) return Promise.resolve(progress);
      if (path.includes("/lessons")) return Promise.resolve(lessons);
      if (path.startsWith("/courses/")) return Promise.resolve(course);
      return Promise.resolve([]);
    });

    // Kick auth.load() (sets loading:true) but do not await — the page mounts
    // while auth is unresolved.
    const loading = auth.load();
    render(CourseDetailPage);
    // Course chrome is visible, but progress is not yet known.
    await waitFor(() => expect(document.querySelector('[data-lesson="l1"]')).toBeTruthy());

    // Auth resolves to the student now.
    resolveMe(student);
    await loading;

    await waitFor(() =>
      expect(get.mock.calls.some((c) => String(c[0]).includes("course_id=c1"))).toBe(true),
    );
    await waitFor(() =>
      expect(screen.getByRole("progressbar", { name: "Progres pelajaran" })).toBeTruthy(),
    );
  });
});
