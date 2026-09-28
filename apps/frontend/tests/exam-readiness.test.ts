// @vitest-environment jsdom
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, cleanup, waitFor } from "@testing-library/svelte";

vi.mock("$app/stores", () => ({
  page: {
    subscribe: (fn: (v: unknown) => void) => (
      fn({ params: { id: "ex1" }, url: new URL("http://x/teacher/exams/ex1") }),
      () => {}
    ),
  },
}));
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

import { auth } from "$lib/stores/auth";
import TeacherExamPage from "$routes-panel/teacher/exams/[id]/+page.svelte";

const teacher = {
  id: "t1",
  email: "teacher@test.com",
  full_name: "Guru Test",
  roles: ["teacher"],
  is_active: true,
  chain_user_ref: "0x0",
  created_at: "2026-01-01T00:00:00Z",
};

function exam(over: Record<string, unknown> = {}, questions: unknown[] = []) {
  return {
    id: "ex1",
    title: "Ujian Fisika",
    owner_id: "t1",
    duration_minutes: 60,
    passing_score_bp: 6000,
    is_active: false,
    questions,
    ...over,
  };
}

describe("exam publish readiness (W3)", () => {
  beforeEach(() => {
    cleanup();
    get.mockReset();
    post.mockReset();
    auth.setUser(teacher);
  });
  afterEach(() => auth.setUser(null));

  it("blocks publish when there are no questions", async () => {
    get.mockImplementation((path: string) => {
      if (path === "/exams/ex1") return Promise.resolve(exam({}, []));
      if (path === "/exams/ex1/questions") return Promise.resolve([]);
      return Promise.resolve([]);
    });

    render(TeacherExamPage);
    await waitFor(() =>
      expect(document.querySelector('[data-role="exam-readiness"]')).toBeTruthy(),
    );
    expect(screen.getByText(/Perlu tindakan/)).toBeTruthy();
    const publishBtn = screen.getByRole("button", { name: /Terbitkan ujian/ }) as HTMLButtonElement;
    expect(publishBtn.disabled).toBe(true);
  });

  it("flags pending drafts as a blocker", async () => {
    const pending = {
      id: "q1",
      prompt: "Soal",
      qtype: "essay",
      position: 0,
      correct_answer: "x",
      review_status: "pending",
      options: [],
    };
    get.mockImplementation((path: string) => {
      if (path === "/exams/ex1") return Promise.resolve(exam({}, [pending]));
      if (path === "/exams/ex1/questions") return Promise.resolve([pending]);
      return Promise.resolve([]);
    });

    render(TeacherExamPage);
    await waitFor(() =>
      expect(document.querySelector('[data-role="exam-readiness"]')).toBeTruthy(),
    );
    expect(screen.getByText(/menunggu disetujui/i)).toBeTruthy();
  });

  it("allows publish when all checks pass", async () => {
    const ok = {
      id: "q1",
      prompt: "Soal siap",
      qtype: "essay",
      position: 0,
      correct_answer: "x",
      review_status: "approved",
      options: [],
    };
    get.mockImplementation((path: string) => {
      if (path === "/exams/ex1") return Promise.resolve(exam({}, [ok]));
      if (path === "/exams/ex1/questions") return Promise.resolve([ok]);
      return Promise.resolve([]);
    });

    render(TeacherExamPage);
    await waitFor(() =>
      expect(document.querySelector('[data-role="exam-readiness"]')).toBeTruthy(),
    );
    expect(screen.getByText(/^Siap$/)).toBeTruthy();
    const publishBtn = screen.getByRole("button", { name: /Terbitkan ujian/ }) as HTMLButtonElement;
    expect(publishBtn.disabled).toBe(false);
  });
});
