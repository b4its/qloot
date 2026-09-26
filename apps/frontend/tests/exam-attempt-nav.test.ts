// @vitest-environment jsdom
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, cleanup, fireEvent } from "@testing-library/svelte";

vi.mock("$app/stores", () => ({
  page: {
    subscribe: (fn: (v: unknown) => void) => (
      fn({
        params: { examId: "ex-102" },
        url: new URL("http://localhost:3000/exams/ex-102/attempt?attempt=att-2"),
      }),
      () => {}
    ),
  },
}));

const mockGoto = vi.fn();
vi.mock("$app/navigation", () => ({
  goto: (...args: unknown[]) => mockGoto(...args),
}));

const get = vi.fn();
const put = vi.fn();
const post = vi.fn();

vi.mock("../src/lib/api/client", () => ({
  API_BASE: "http://localhost:8000",
  ApiError: class ApiError extends Error {
    status = 0;
  },
  api: {
    get: (...a: unknown[]) => get(...a),
    put: (...a: unknown[]) => put(...a),
    post: (...a: unknown[]) => post(...a),
  },
}));

import ExamAttemptPage from "../src/routes/(site)/exams/[examId]/attempt/+page.svelte";

const mockExamData = {
  id: "ex-102",
  title: "Simulasi Ujian Matematika Dasar",
  duration_minutes: 60,
  questions: [
    {
      id: "q-1",
      prompt: "Berapa hasil dari 15 x 12?",
      qtype: "multiple_choice",
      options: [
        { label: "A", text: "180" },
        { label: "B", text: "150" },
      ],
    },
    {
      id: "q-2",
      prompt: "Apakah 17 adalah bilangan prima?",
      qtype: "true_false",
    },
  ],
};

const mockAttemptData = {
  id: "att-2",
  exam_id: "ex-102",
  user_id: "user-1",
  started_at: new Date(Date.now() - 5 * 60_000).toISOString(),
  expires_at: new Date(Date.now() + 55 * 60_000).toISOString(),
  status: "in_progress",
};

describe("exam attempt page UI/UX overhaul", () => {
  beforeEach(() => {
    cleanup();
    get.mockReset();
    put.mockReset();
    post.mockReset();
    mockGoto.mockReset();

    get.mockImplementation(async (path: string) => {
      if (path === "/exams/ex-102") return mockExamData;
      if (path === "/attempts/att-2") return mockAttemptData;
      if (path === "/attempts/att-2/questions") return mockExamData.questions;
      if (path === "/attempts/att-2/result") {
        return {
          answers: [
            {
              question_id: "q-1",
              answer_text: "A",
            },
          ],
        };
      }
      return {};
    });
    put.mockResolvedValue({});
    post.mockResolvedValue({});
  });

  afterEach(() => cleanup());

  it("renders exam title, progress indicator, question badge, and navigator palette", async () => {
    render(ExamAttemptPage);
    expect(await screen.findByText("Simulasi Ujian Matematika Dasar")).toBeTruthy();

    // Check answered progress
    expect(screen.getByText(/Terjawab:/)).toBeTruthy();
    expect(screen.getByText(/dari 2 soal/)).toBeTruthy();

    // Check question title and type badge
    expect(screen.getByText("Soal 1 dari 2")).toBeTruthy();
    expect(screen.getByText("Pilihan Ganda")).toBeTruthy();

    // Check navigator sidebar
    expect(screen.getByText("Navigasi Soal")).toBeTruthy();
    expect(screen.getByText("1/2 (50%)")).toBeTruthy();
  });

  it("toggles doubt flag when clicking 'Tandai Ragu-ragu'", async () => {
    render(ExamAttemptPage);
    expect(await screen.findByText("Simulasi Ujian Matematika Dasar")).toBeTruthy();

    const flagBtn = screen.getByRole("button", { name: /Tandai Ragu-ragu/ });
    expect(flagBtn).toBeTruthy();

    await fireEvent.click(flagBtn);
    expect(screen.getByText("Ragu-ragu (Ditandai)")).toBeTruthy();

    await fireEvent.click(flagBtn);
    expect(screen.getByText("Tandai Ragu-ragu")).toBeTruthy();
  });

  it("opens confirmation modal on submit click, shows unanswered warning, and confirms submit", async () => {
    render(ExamAttemptPage);
    expect(await screen.findByText("Simulasi Ujian Matematika Dasar")).toBeTruthy();

    // Top submit button
    const submitBtn = screen.getByRole("button", { name: "Kumpulkan" });
    await fireEvent.click(submitBtn);

    // Modal appears
    expect(screen.getByText("Konfirmasi Pengumpulan Ujian")).toBeTruthy();
    expect(screen.getByText(/Masih ada 1 soal yang belum dijawab!/)).toBeTruthy();
    expect(screen.getByText("#2")).toBeTruthy(); // jump shortcut to question 2

    // Confirm submission
    const confirmBtn = screen.getByRole("button", { name: "Ya, Kumpulkan Sekarang" });
    await fireEvent.click(confirmBtn);

    await vi.waitFor(() => {
      expect(post).toHaveBeenCalledWith("/attempts/att-2/submit");
    });
  });
});
