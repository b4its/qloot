// @vitest-environment jsdom
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, cleanup, waitFor } from "@testing-library/svelte";

vi.mock("$app/stores", () => ({
  page: {
    subscribe: (fn: (v: unknown) => void) => (
      fn({ params: { examId: "e1" }, url: new URL("http://x/exams/e1") }),
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

import ExamDetailPage from "$routes-site/exams/[examId]/+page.svelte";
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

const exam = {
  id: "e1",
  title: "Kuis Bab 1",
  owner_id: "t1",
  duration_minutes: 15,
  status: "published",
  is_active: true,
  passing_score_bp: 6000,
  max_attempts: 3,
  question_count: 5,
  mc_count: 5,
  essay_count: 0,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
  instructions: "Kerjakan tanpa kalkulator.\nPeriksa kembali jawabanmu.",
};

describe("exam detail — best score, pass/fail, and resume", () => {
  beforeEach(() => {
    cleanup();
    get.mockReset();
    auth.setUser(student);
  });
  afterEach(() => auth.setUser(null));

  it("requests attempts scoped to the exam", async () => {
    get.mockImplementation((path: string) => {
      if (path.startsWith("/exams/")) return Promise.resolve(exam);
      if (path.startsWith("/attempts")) return Promise.resolve([]);
      return Promise.resolve([]);
    });
    render(ExamDetailPage);
    await waitFor(() =>
      expect(get.mock.calls.some((c) => String(c[0]).includes("exam_id=e1"))).toBe(true),
    );
  });

  it("shows the best score and pass status from attempts", async () => {
    get.mockImplementation((path: string) => {
      if (path.startsWith("/exams/")) return Promise.resolve(exam);
      if (path.startsWith("/attempts"))
        return Promise.resolve([
          {
            id: "a1",
            exam_id: "e1",
            user_id: "u1",
            attempt_number: 1,
            status: "graded",
            score_bp: 8000,
            passed: true,
            started_at: "2026-01-01T00:00:00Z",
          },
        ]);
      return Promise.resolve([]);
    });
    render(ExamDetailPage);
    await waitFor(() =>
      expect(document.querySelector('[data-role="best-score"]')?.textContent?.trim()).toBe("80.0%"),
    );
    expect(screen.getByText("Sudah lulus")).toBeTruthy();
  });

  it("surfaces an in-progress attempt to resume", async () => {
    get.mockImplementation((path: string) => {
      if (path.startsWith("/exams/")) return Promise.resolve(exam);
      if (path.startsWith("/attempts"))
        return Promise.resolve([
          {
            id: "a9",
            exam_id: "e1",
            user_id: "u1",
            attempt_number: 1,
            status: "in_progress",
            score_bp: null,
            passed: null,
            started_at: "2026-01-01T00:00:00Z",
          },
        ]);
      return Promise.resolve([]);
    });
    render(ExamDetailPage);
    await waitFor(() => expect(screen.getByText(/belum diselesaikan/)).toBeTruthy());
    expect(screen.getByText("Lanjutkan pengerjaan →")).toBeTruthy();
  });

  it("shows teacher instructions before the student starts", async () => {
    get.mockImplementation((path: string) => {
      if (path.startsWith("/exams/")) return Promise.resolve(exam);
      return Promise.resolve([]);
    });
    render(ExamDetailPage);
    expect(await screen.findByText("Instruksi pengerjaan")).toBeTruthy();
    expect(screen.getByText(/Kerjakan tanpa kalkulator/)).toBeTruthy();
  });

  it("disables starting before the scheduled opening time", async () => {
    get.mockImplementation((path: string) => {
      if (path.startsWith("/exams/")) {
        return Promise.resolve({ ...exam, opens_at: "2999-01-01T00:00:00Z" });
      }
      return Promise.resolve([]);
    });
    render(ExamDetailPage);
    expect(await screen.findByText("Ujian belum dibuka")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Mulai mengerjakan" })).toBeNull();
  });
});
