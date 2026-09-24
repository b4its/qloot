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

vi.mock("$app/stores", () => ({
  page: {
    subscribe: (fn: (v: unknown) => void) => (
      fn({
        params: { courseId: "c1", lessonId: "l1" },
        url: new URL("http://x/learning/c1/lesson/l1"),
      }),
      () => {}
    ),
  },
}));

import LessonPage from "$routes-site/learning/[courseId]/lesson/[lessonId]/+page.svelte";

const lesson = {
  id: "l1",
  course_id: "c1",
  title: "Fotosintesis",
  position: 1,
  content_md: "Isi materi",
  created_at: "2026-01-01T00:00:00Z",
};

const material = {
  id: "m1",
  owner_id: "t1",
  filename: "Biologi.pdf",
  content_type: "application/pdf",
  size_bytes: 100,
  status: "ready",
  created_at: "2026-01-01T00:00:00Z",
};

describe("student learning — material panel (LEARN-04)", () => {
  beforeEach(() => {
    cleanup();
    get.mockReset();
    post.mockReset();
    get.mockImplementation((path: string) => {
      if (path === "/lessons/l1") return Promise.resolve(lesson);
      if (path.startsWith("/lessons/l1/materials")) return Promise.resolve([material]);
      if (path === "/materials/m1/summary")
        return Promise.resolve({ summary: "Ringkasan singkat", key_points: ["Poin satu"] });
      return Promise.resolve([]);
    });
  });
  afterEach(() => cleanup());

  it("lists the lesson's materials with a download link", async () => {
    render(LessonPage);
    expect(await screen.findByText("Biologi.pdf")).toBeTruthy();
    const link = screen.getByRole("link", { name: /unduh/i });
    expect(link.getAttribute("href")).toBe("http://localhost:8000/api/v1/materials/m1/download");
  });

  it("requests an AI summary when the assistant panel is opened", async () => {
    render(LessonPage);
    await screen.findByText("Biologi.pdf");
    await fireEvent.click(screen.getByRole("button", { name: /asisten/i }));
    await fireEvent.click(screen.getByRole("button", { name: /ringkas materi/i }));
    await waitFor(() => expect(get).toHaveBeenCalledWith("/materials/m1/summary"));
    expect(await screen.findByText(/Ringkasan singkat/)).toBeTruthy();
  });

  it("asks a grounded question about the material", async () => {
    post.mockResolvedValue({ answer: "Karena klorofil menyerap cahaya.", confidence_bp: 8000 });
    render(LessonPage);
    await screen.findByText("Biologi.pdf");
    await fireEvent.click(screen.getByRole("button", { name: /asisten/i }));
    const input = screen.getByPlaceholderText(/tanyakan sesuatu/i);
    await fireEvent.input(input, { target: { value: "Mengapa daun hijau?" } });
    await fireEvent.click(screen.getByRole("button", { name: /^tanya$/i }));
    await waitFor(() =>
      expect(post).toHaveBeenCalledWith("/materials/m1/ask", { question: "Mengapa daun hijau?" }),
    );
    expect(await screen.findByText(/Karena klorofil menyerap cahaya\./)).toBeTruthy();
  });

  it("shows an empty state when the lesson has no materials", async () => {
    get.mockImplementation((path: string) => {
      if (path === "/lessons/l1") return Promise.resolve(lesson);
      if (path.startsWith("/lessons/l1/materials")) return Promise.resolve([]);
      return Promise.resolve([]);
    });
    render(LessonPage);
    expect(await screen.findByText(/belum ada materi pdf/i)).toBeTruthy();
  });
});
