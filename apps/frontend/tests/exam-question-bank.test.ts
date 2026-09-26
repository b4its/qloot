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
  prompt: "Soal Nomor Satu yang sudah ada",
  qtype: "multiple_choice",
  position: 0,
  correct_answer: null,
  review_status: "approved",
  options: [{ label: "A", text: "Pilihan A", is_correct: true }],
};

const sampleExam = {
  id: "ex1",
  title: "Ujian Biologi",
  owner_id: "t1",
  duration_minutes: 45,
  passing_score_bp: 6000,
  is_active: false,
  questions: [q1],
};

const bankItems = [
  { id: "bq-1", prompt: "Soal Nomor Satu yang sudah ada", qtype: "multiple_choice" },
  { id: "bq-2", prompt: "Jelaskan proses metabolisme sel", qtype: "essay" },
  { id: "bq-3", prompt: "Apakah air mendidih pada suhu 100C?", qtype: "true_false" },
];

describe("teacher exam question bank import and filtering", () => {
  beforeEach(() => {
    cleanup();
    get.mockReset();
    post.mockReset();
    patch.mockReset();
    del.mockReset();
    auth.setUser(teacher);

    get.mockImplementation((path: string) => {
      if (path === "/exams/ex1") return Promise.resolve(sampleExam);
      if (path === "/exams/ex1/questions") return Promise.resolve([q1]);
      if (typeof path === "string" && path.startsWith("/questions/bank"))
        return Promise.resolve(bankItems);
      return Promise.resolve([]);
    });
  });

  afterEach(() => auth.setUser(null));

  it("opens bank drawer and displays question items with badges and duplicate indicators", async () => {
    render(TeacherExamPage);
    expect(await screen.findByText(/Soal Nomor Satu yang sudah ada/)).toBeTruthy();

    const openBankBtn = screen.getByText("Impor dari bank soal");
    await fireEvent.click(openBankBtn);

    await waitFor(() => {
      expect(screen.getByPlaceholderText("Cari dalam bank soal...")).toBeTruthy();
      expect(screen.getByText("Jelaskan proses metabolisme sel")).toBeTruthy();
    });

    // Already attached question has disabled button with text "Ada"
    const adaButtons = screen.getAllByRole("button", { name: "Ada" });
    expect(adaButtons.length).toBe(1);
    expect((adaButtons[0] as HTMLButtonElement).disabled).toBe(true);

    // New question has enabled "Impor" button
    const imporButtons = screen.getAllByRole("button", { name: "Impor" });
    expect(imporButtons.length).toBe(2);
  });

  it("filters question bank by search query", async () => {
    render(TeacherExamPage);
    await screen.findByText(/Soal Nomor Satu yang sudah ada/);

    await fireEvent.click(screen.getByText("Impor dari bank soal"));
    await screen.findByText("Jelaskan proses metabolisme sel");

    const searchInput = screen.getByPlaceholderText("Cari dalam bank soal...");
    await fireEvent.input(searchInput, { target: { value: "metabolisme" } });

    await waitFor(() => {
      expect(screen.getByText("Jelaskan proses metabolisme sel")).toBeTruthy();
      expect(screen.queryByText("Apakah air mendidih pada suhu 100C?")).toBeNull();
    });
  });

  it("imports a question from the bank", async () => {
    post.mockResolvedValue({ id: "cloned-1", prompt: "Jelaskan proses metabolisme sel" });
    render(TeacherExamPage);
    await screen.findByText(/Soal Nomor Satu yang sudah ada/);

    await fireEvent.click(screen.getByText("Impor dari bank soal"));
    await screen.findByText("Jelaskan proses metabolisme sel");

    const imporButtons = screen.getAllByRole("button", { name: "Impor" });
    await fireEvent.click(imporButtons[0]);

    await waitFor(() => {
      expect(post).toHaveBeenCalledWith("/exams/ex1/questions/attach", {
        question_id: "bq-2",
      });
    });
  });
});
