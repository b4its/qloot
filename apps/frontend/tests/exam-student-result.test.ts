// @vitest-environment jsdom
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, cleanup } from "@testing-library/svelte";

vi.mock("$app/stores", () => ({
  page: {
    subscribe: (fn: (v: unknown) => void) => (
      fn({
        params: { examId: "ex-101" },
        url: new URL("http://localhost:3000/exams/ex-101/result?attempt=att-1"),
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

import StudentResultPage from "../src/routes/(site)/exams/[examId]/result/+page.svelte";

const mockResultData = {
  exam: {
    id: "ex-101",
    title: "Ujian Akhir Semester Fisika",
    passing_score_bp: 7000,
  },
  attempt: {
    id: "att-1",
    attempt_number: 1,
    status: "graded",
    score_bp: 8500,
    passed: true,
  },
  answers: [
    {
      question_id: "q-1",
      score_bp: 5000,
      max_score_bp: 5000,
      answer_text: "A",
      feedback: "Tepat sekali.",
    },
    {
      question_id: "q-2",
      score_bp: 3500,
      max_score_bp: 5000,
      answer_text: "true",
      feedback: null,
    },
  ],
  questions: [
    {
      id: "q-1",
      prompt: "Berapa gravitasi bumi standar?",
      qtype: "multiple_choice",
      options: [
        { label: "A", text: "9.8 m/s^2", is_correct: true },
        { label: "B", text: "10.5 m/s^2", is_correct: false },
      ],
    },
    {
      id: "q-2",
      prompt: "Massa jenis air adalah 1 g/cm3?",
      qtype: "true_false",
      correct_answer: "true",
    },
  ],
};

describe("student exam result page UX overhaul", () => {
  beforeEach(() => {
    cleanup();
    get.mockReset();
    post.mockReset();
    get.mockResolvedValue(mockResultData);
  });

  afterEach(() => cleanup());

  it("renders exam title, overall score, passing badge, and summary metrics", async () => {
    render(StudentResultPage);
    expect(await screen.findByText("Ujian Akhir Semester Fisika")).toBeTruthy();
    expect(screen.getByText("85.0%")).toBeTruthy();
    expect(screen.getByText("Lulus")).toBeTruthy();

    expect(screen.getByText("Total Soal")).toBeTruthy();
    expect(screen.getByText("Batas Kelulusan")).toBeTruthy();
    expect(screen.getByText("Memenuhi syarat")).toBeTruthy();
  });

  it("renders question index, question type badge, and option status", async () => {
    render(StudentResultPage);
    expect(await screen.findByText("Berapa gravitasi bumi standar?")).toBeTruthy();
    expect(screen.getByText("#1")).toBeTruthy();
    expect(screen.getByText("#2")).toBeTruthy();
    expect(screen.getByText("Pilihan Ganda")).toBeTruthy();
    expect(screen.getByText("Benar/Salah")).toBeTruthy();
    expect(screen.getByText("Pilihanmu")).toBeTruthy();
  });
});
