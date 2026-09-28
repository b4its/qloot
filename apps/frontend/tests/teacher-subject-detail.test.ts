// @vitest-environment jsdom
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, fireEvent, cleanup, waitFor } from "@testing-library/svelte";

vi.mock("$app/stores", () => ({
  page: {
    subscribe: (fn: (v: unknown) => void) => (
      fn({ params: { id: "c1" }, url: new URL("http://x/teacher/subjects/c1") }),
      () => {}
    ),
  },
}));
vi.mock("$app/navigation", () => ({ goto: vi.fn() }));

const get = vi.fn();
const patch = vi.fn();
const del = vi.fn();
const { post } = vi.hoisted(() => ({ post: vi.fn() }));
vi.mock("../src/lib/api/client", () => ({
  API_BASE: "http://localhost:8000",
  ApiError: class ApiError extends Error {
    status = 0;
  },
  api: {
    get: (...a: unknown[]) => get(...a),
    post: (...a: unknown[]) => post(...a),
    put: vi.fn(),
    patch: (...a: unknown[]) => patch(...a),
    delete: (...a: unknown[]) => del(...a),
  },
}));

import SubjectDetailPage from "$routes-panel/teacher/subjects/[id]/+page.svelte";
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

const course = {
  id: "c1",
  title: "Fisika Dasar",
  slug: "fisika",
  owner_id: "t1",
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
  { id: "l2", course_id: "c1", title: "Materi B", position: 1, is_published: false },
  { id: "l3", course_id: "c1", title: "Materi C", position: 2, is_published: true },
];

describe("teacher subject detail — lesson metrics, dirty-save, and delete confirm", () => {
  beforeEach(() => {
    cleanup();
    get.mockReset();
    patch.mockReset();
    del.mockReset();
    post.mockReset();
    auth.setUser(teacher);
    get.mockImplementation((path: string) => {
      if (path.includes("/lessons")) return Promise.resolve(lessons);
      if (path.startsWith("/courses/")) return Promise.resolve(course);
      return Promise.resolve([]);
    });
    patch.mockResolvedValue(course);
    del.mockResolvedValue({});
  });
  afterEach(() => auth.setUser(null));

  it("shows published/draft lesson metrics", async () => {
    render(SubjectDetailPage);
    await waitFor(() => expect(screen.getByText("2 terbit · 1 draf")).toBeTruthy());
  });

  it("renders the campaign stepper with a next-step action", async () => {
    get.mockImplementation((path: string) => {
      if (path.includes("/lessons")) return Promise.resolve(lessons);
      if (path.startsWith("/exams")) return Promise.resolve([]);
      if (path.startsWith("/quests")) return Promise.resolve([]);
      if (path.startsWith("/courses/")) return Promise.resolve(course);
      return Promise.resolve([]);
    });

    render(SubjectDetailPage);
    await waitFor(() =>
      expect(document.querySelector('[data-role="campaign-stepper"]')).toBeTruthy(),
    );
    const stepEls = document.querySelectorAll('[data-role="campaign-step"]');
    expect(stepEls.length).toBe(5);
    // Course + material are done (title set, lessons exist).
    const states = Array.from(stepEls).map((el) => el.getAttribute("data-state"));
    expect(states[0]).toBe("done");
    expect(states[1]).toBe("done");
    // The next-step call-to-action is shown with the first unfinished step.
    expect(document.querySelector('[data-role="campaign-next"]')).toBeTruthy();
    // A student-facing preview link opens the learning view in a new tab.
    const preview = document.querySelector('[data-role="campaign-preview"]') as HTMLAnchorElement;
    expect(preview).toBeTruthy();
    expect(preview.getAttribute("href")).toBe("/learning/c1");
    expect(preview.getAttribute("target")).toBe("_blank");
  });

  it("disables save until the course form changes", async () => {
    render(SubjectDetailPage);
    await waitFor(() => expect(screen.getByRole("button", { name: /Tersimpan/i })).toBeTruthy());
    const save = screen.getByRole("button", { name: /Tersimpan/i }) as HTMLButtonElement;
    expect(save.disabled).toBe(true);

    const titleInput = document.querySelector("input.input") as HTMLInputElement;
    await fireEvent.input(titleInput, { target: { value: "Fisika Lanjut" } });
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /Simpan perubahan/i })).toBeTruthy(),
    );
  });

  it("confirms before deleting a lesson", async () => {
    render(SubjectDetailPage);
    await waitFor(() =>
      expect(screen.getAllByRole("button", { name: "Hapus materi" }).length).toBe(3),
    );

    const delButtons = screen.getAllByRole("button", { name: "Hapus materi" });
    await fireEvent.click(delButtons[0]);
    expect(screen.getByText("Hapus Materi")).toBeTruthy();
    expect(del).not.toHaveBeenCalled();

    const confirm = document.querySelector(
      '[data-role="confirm-delete-lesson"]',
    ) as HTMLButtonElement;
    await fireEvent.click(confirm);
    await waitFor(() => expect(del).toHaveBeenCalledWith("/lessons/l1"));
  });

  it("edits cover URL and publish state", async () => {
    render(SubjectDetailPage);
    await waitFor(() => expect(screen.getByRole("button", { name: /Tersimpan/i })).toBeTruthy());

    const cover = screen.getByPlaceholderText("https://…") as HTMLInputElement;
    await fireEvent.input(cover, { target: { value: "https://img/x.png" } });
    // The course publish toggle is the first checkbox (the new-lesson one comes later).
    const publishToggle = screen.getAllByRole("checkbox")[0] as HTMLInputElement;
    await fireEvent.click(publishToggle);

    await fireEvent.click(screen.getByRole("button", { name: /Simpan perubahan/i }));
    await waitFor(() =>
      expect(patch).toHaveBeenCalledWith(
        "/courses/c1",
        expect.objectContaining({ cover_url: "https://img/x.png", is_published: false }),
      ),
    );
  });

  it("adds a lesson with video URL and publish state", async () => {
    post.mockResolvedValue({});
    render(SubjectDetailPage);
    await waitFor(() => expect(screen.getByPlaceholderText("Judul materi baru")).toBeTruthy());

    await fireEvent.input(screen.getByPlaceholderText("Judul materi baru"), {
      target: { value: "Materi Baru" },
    });
    await fireEvent.input(screen.getByPlaceholderText("URL video (opsional)"), {
      target: { value: "https://vid/x.mp4" },
    });
    await fireEvent.click(screen.getByRole("button", { name: /Tambah materi/i }));

    await waitFor(() =>
      expect(post).toHaveBeenCalledWith(
        "/courses/c1/lessons",
        expect.objectContaining({ title: "Materi Baru", video_url: "https://vid/x.mp4" }),
      ),
    );
  });
});
