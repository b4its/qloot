// @vitest-environment jsdom
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, cleanup, waitFor } from "@testing-library/svelte";

// Controllable page store so we can simulate same-route param changes (the way
// clicking prev/next or the lesson dropdown navigates within the lesson route).
const { pageStore } = vi.hoisted(() => {
  let value: unknown;
  const subs = new Set<(v: unknown) => void>();
  const store = {
    subscribe(fn: (v: unknown) => void) {
      subs.add(fn);
      fn(value);
      return () => subs.delete(fn);
    },
    set(v: unknown) {
      value = v;
      subs.forEach((fn) => fn(v));
    },
  };
  store.set({
    params: { courseId: "c1", lessonId: "l1" },
    url: new URL("http://x/learning/c1/lesson/l1"),
  });
  return { pageStore: store };
});
vi.mock("$app/stores", () => ({ page: pageStore }));
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

import { auth } from "$lib/stores/auth";
import LessonPage from "$routes-site/learning/[courseId]/lesson/[lessonId]/+page.svelte";

const student = {
  id: "u1",
  email: "s@x.com",
  full_name: "Student",
  is_active: true,
  chain_user_ref: "0x0",
  created_at: "2026-01-01T00:00:00Z",
  roles: ["student"],
};

const lessons = [
  { id: "l1", course_id: "c1", title: "Materi A", position: 0, is_published: true },
  { id: "l2", course_id: "c1", title: "Materi B", position: 1, is_published: true },
];

function lesson(id: string) {
  return {
    id,
    course_id: "c1",
    title: id === "l1" ? "Fotosintesis" : "Respirasi",
    position: 0,
    content_md: `Isi ${id}`,
    created_at: "2026-01-01T00:00:00Z",
  };
}

describe("lesson page — same-route navigation", () => {
  beforeEach(() => {
    cleanup();
    get.mockReset();
    auth.setUser(student);
    pageStore.set({
      params: { courseId: "c1", lessonId: "l1" },
      url: new URL("http://x/learning/c1/lesson/l1"),
    });
    get.mockImplementation((path: string) => {
      if (path === "/lessons/l1") return Promise.resolve(lesson("l1"));
      if (path === "/lessons/l2") return Promise.resolve(lesson("l2"));
      if (path === "/courses/c1") return Promise.resolve({ id: "c1", title: "Biologi" });
      if (path === "/courses/c1/lessons") return Promise.resolve(lessons);
      if (path.startsWith("/me/learning-progress")) return Promise.resolve([]);
      return Promise.resolve([]);
    });
  });
  afterEach(() => {
    auth.setUser(null);
    cleanup();
  });

  it("reloads the lesson when the lessonId param changes", async () => {
    render(LessonPage);
    expect(await screen.findByText("Fotosintesis")).toBeTruthy();

    // Navigate to the next lesson (same route, different param).
    pageStore.set({
      params: { courseId: "c1", lessonId: "l2" },
      url: new URL("http://x/learning/c1/lesson/l2"),
    });

    expect(await screen.findByText("Respirasi")).toBeTruthy();
    expect(screen.queryByText("Fotosintesis")).toBeNull();
    await waitFor(() => expect(get).toHaveBeenCalledWith("/lessons/l2"));
  });
});
