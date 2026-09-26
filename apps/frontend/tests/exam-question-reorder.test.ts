// @vitest-environment jsdom
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, fireEvent, cleanup, waitFor } from "@testing-library/svelte";

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
const patch = vi.fn();
const del = vi.fn();

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

const q1 = {
  id: "q-1",
  prompt: "Soal Nomor Satu",
  qtype: "essay",
  position: 0,
  correct_answer: "Kunci 1",
  review_status: "approved",
  options: [],
};

const q2 = {
  id: "q-2",
  prompt: "Soal Nomor Dua",
  qtype: "essay",
  position: 1,
  correct_answer: "Kunci 2",
  review_status: "approved",
  options: [],
};

const sampleExam = {
  id: "ex1",
  title: "Ujian Fisika",
  owner_id: "t1",
  duration_minutes: 60,
  passing_score_bp: 6000,
  is_active: false,
  questions: [q1, q2],
};

describe("teacher exam question reordering", () => {
  beforeEach(() => {
    cleanup();
    get.mockReset();
    post.mockReset();
    patch.mockReset();
    del.mockReset();
    auth.setUser(teacher);

    get.mockImplementation((path: string) => {
      if (path === "/exams/ex1") return Promise.resolve(sampleExam);
      if (path === "/exams/ex1/questions") return Promise.resolve([q1, q2]);
      return Promise.resolve([]);
    });
  });

  afterEach(() => auth.setUser(null));

  it("renders move up and move down buttons for multiple questions", async () => {
    render(TeacherExamPage);
    expect(await screen.findByText(/Soal Nomor Satu/)).toBeTruthy();
    expect(screen.getByText(/Soal Nomor Dua/)).toBeTruthy();

    const upButtons = screen.getAllByRole("button", { name: "Pindah ke atas" });
    const downButtons = screen.getAllByRole("button", { name: "Pindah ke bawah" });

    expect(upButtons.length).toBe(2);
    expect(downButtons.length).toBe(2);

    // First question: up is disabled, down is enabled
    expect((upButtons[0] as HTMLButtonElement).disabled).toBe(true);
    expect((downButtons[0] as HTMLButtonElement).disabled).toBe(false);

    // Second (last) question: up is enabled, down is disabled
    expect((upButtons[1] as HTMLButtonElement).disabled).toBe(false);
    expect((downButtons[1] as HTMLButtonElement).disabled).toBe(true);
  });

  it("calls /exams/{id}/questions/reorder with reordered question ids when clicked", async () => {
    post.mockResolvedValue([q2, q1]);
    render(TeacherExamPage);
    expect(await screen.findByText(/Soal Nomor Satu/)).toBeTruthy();

    const downButtons = screen.getAllByRole("button", { name: "Pindah ke bawah" });
    await fireEvent.click(downButtons[0]);

    await waitFor(() => {
      expect(post).toHaveBeenCalledWith("/exams/ex1/questions/reorder", {
        question_ids: ["q-2", "q-1"],
      });
    });
  });
});
