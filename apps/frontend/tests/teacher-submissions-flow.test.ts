// @vitest-environment jsdom
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, cleanup, fireEvent, waitFor } from "@testing-library/svelte";

vi.mock("$app/navigation", () => ({
  goto: vi.fn(),
}));

const get = vi.fn();

vi.mock("../src/lib/api/client", () => ({
  API_BASE: "http://localhost:8000",
  ApiError: class ApiError extends Error {
    status = 0;
  },
  api: {
    get: (...a: unknown[]) => get(...a),
  },
}));

vi.mock("../src/lib/stores/auth", () => ({
  auth: {
    subscribe: (fn: (v: unknown) => void) => {
      fn({
        user: { id: "u-teacher", email: "teacher@test.com", role: "teacher" },
        loading: false,
      });
      return () => {};
    },
  },
  hasRole: (user: { role?: string } | null, role: string) => user?.role === role,
}));

import SubmissionsPage from "../src/routes/(panel)/teacher/submissions/+page.svelte";

const mockExams = [
  { id: "e-1", title: "Ujian Matematika Dasar" },
  { id: "e-2", title: "Ujian Biologi Sel" },
];

const mockAnalytics = {
  exams: 5,
  graded_attempts: 42,
  average_score_bp: 8250,
  pass_rate_bp: 9000,
  winners: 8,
  opc_awarded: 250,
};

const mockSubmissions = [
  {
    student_id: "s-1",
    student_name: "Ahmad Siswa",
    exam_id: "e-1",
    exam_title: "Ujian Matematika Dasar",
    question_id: "q-101",
    prompt: "Berapa 12 x 12?",
    qtype: "multiple_choice",
    answer_text: "A",
    answer_display: "144",
    correct_answer: "A",
    correct_display: "144",
    is_correct: true,
    score_bp: 10000,
    max_score_bp: 10000,
    feedback: "Jawaban tepat dan akurat.",
    saved_at: "2026-09-26T10:00:00Z",
  },
  {
    student_id: "s-2",
    student_name: "Budi Siswa",
    exam_id: "e-1",
    exam_title: "Ujian Matematika Dasar",
    question_id: "q-102",
    prompt: "Berapa akar dari 81?",
    qtype: "multiple_choice",
    answer_text: "C",
    answer_display: "7",
    correct_answer: "B",
    correct_display: "9",
    is_correct: false,
    score_bp: 0,
    max_score_bp: 10000,
    feedback: "Akar kuadrat dari 81 adalah 9.",
    saved_at: "2026-09-26T10:05:00Z",
  },
  {
    student_id: "s-3",
    student_name: "Citra Siswa",
    exam_id: "e-2",
    exam_title: "Ujian Biologi Sel",
    question_id: "q-201",
    prompt: "Jelaskan fungsi mitokondria.",
    qtype: "essay",
    answer_text: "Mitokondria adalah pembangkit energi sel (ATP).",
    correct_answer: null,
    correct_display: null,
    is_correct: null,
    score_bp: 8500,
    max_score_bp: 10000,
    feedback: "Penjelasan baik dan mencakup konsep ATP.",
    saved_at: "2026-09-26T10:10:00Z",
  },
];

describe("Teacher Submissions Flow", () => {
  beforeEach(() => {
    cleanup();
    get.mockReset();

    get.mockImplementation(async (path: string) => {
      if (path.startsWith("/teacher/submissions")) {
        // Mirror the server-side status filter (the component sends ?status=...).
        if (path.includes("status=correct"))
          return mockSubmissions.filter((r) => r.is_correct === true);
        if (path.includes("status=incorrect"))
          return mockSubmissions.filter((r) => r.is_correct === false);
        if (path.includes("status=ungraded"))
          return mockSubmissions.filter((r) => r.is_correct === null);
        return mockSubmissions;
      }
      if (path.startsWith("/exams")) {
        return mockExams;
      }
      if (path === "/teacher/analytics") {
        return mockAnalytics;
      }
      return [];
    });
  });

  afterEach(() => cleanup());

  it("renders header, analytics cards, filters, and submissions table", async () => {
    render(SubmissionsPage);

    expect(await screen.findByText("Ahmad Siswa")).toBeTruthy();
    expect(screen.getByText("Budi Siswa")).toBeTruthy();
    expect(screen.getByText("Citra Siswa")).toBeTruthy();

    // Check analytics metrics
    expect(screen.getByText("Ternilai")).toBeTruthy();
    expect(screen.getByText("42")).toBeTruthy();
    expect(screen.getByText("82.5%")).toBeTruthy();

    // Check filter tabs
    expect(screen.getByRole("button", { name: "Semua" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Benar" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Salah" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Esai/Manual" })).toBeTruthy();

    // Check CSV export button
    expect(screen.getByRole("button", { name: /Ekspor CSV/i })).toBeTruthy();
  });

  it("filters rows by correctness status tabs (server-side)", async () => {
    render(SubmissionsPage);

    expect(await screen.findByText("Ahmad Siswa")).toBeTruthy();

    // Filter Benar — the component re-queries the server with ?status=correct.
    const correctBtn = screen.getByRole("button", { name: "Benar" });
    await fireEvent.click(correctBtn);

    await waitFor(() =>
      expect(get).toHaveBeenCalledWith(expect.stringContaining("status=correct")),
    );
    await waitFor(() => expect(screen.getByText("Ahmad Siswa")).toBeTruthy());
    expect(screen.queryByText("Budi Siswa")).toBeNull();
    expect(screen.queryByText("Citra Siswa")).toBeNull();

    // Filter Salah
    const incorrectBtn = screen.getByRole("button", { name: "Salah" });
    await fireEvent.click(incorrectBtn);

    await waitFor(() => expect(screen.getByText("Budi Siswa")).toBeTruthy());
    expect(screen.queryByText("Ahmad Siswa")).toBeNull();
    expect(screen.queryByText("Citra Siswa")).toBeNull();

    // Filter Esai/Manual
    const essayBtn = screen.getByRole("button", { name: "Esai/Manual" });
    await fireEvent.click(essayBtn);

    await waitFor(() => expect(screen.getByText("Citra Siswa")).toBeTruthy());
    expect(screen.queryByText("Ahmad Siswa")).toBeNull();
    expect(screen.queryByText("Budi Siswa")).toBeNull();

    // Reset to Semua
    const allBtn = screen.getByRole("button", { name: "Semua" });
    await fireEvent.click(allBtn);
    await waitFor(() => expect(screen.getByText("Ahmad Siswa")).toBeTruthy());
    expect(screen.getByText("Budi Siswa")).toBeTruthy();
    expect(screen.getByText("Citra Siswa")).toBeTruthy();
  });

  it("opens inspection modal on Detail click and dismisses it", async () => {
    render(SubmissionsPage);

    expect(await screen.findByText("Ahmad Siswa")).toBeTruthy();

    const detailButtons = screen.getAllByRole("button", { name: "Detail" });
    expect(detailButtons.length).toBe(3);

    // Click first detail button (Ahmad Siswa)
    await fireEvent.click(detailButtons[0]);

    expect(screen.getByText("Detail Pengumpulan Siswa")).toBeTruthy();
    expect(screen.getAllByText("Berapa 12 x 12?").length).toBe(2);
    expect(screen.getByText("Kunci / Jawaban Benar")).toBeTruthy();
    expect(screen.getAllByText("Umpan Balik AI").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Jawaban tepat dan akurat.").length).toBe(2);

    // Close modal via Tutup button
    const closeBtns = screen.getAllByRole("button", { name: "Tutup" });
    await fireEvent.click(closeBtns[0]);

    expect(screen.queryByText("Detail Pengumpulan Siswa")).toBeNull();
  });

  it("handles search query submission to backend", async () => {
    render(SubmissionsPage);

    expect(await screen.findByText("Ahmad Siswa")).toBeTruthy();

    const searchInput = screen.getByPlaceholderText("Cari siswa, ujian, atau soal...");
    await fireEvent.input(searchInput, { target: { value: "Ahmad" } });
    await fireEvent.keyDown(searchInput, { key: "Enter" });

    await waitFor(() => {
      expect(get).toHaveBeenCalledWith(expect.stringContaining("q=Ahmad"));
    });
  });

  it("triggers CSV export download", async () => {
    const createObjectURL = vi.fn(() => "blob:mock-url");
    const revokeObjectURL = vi.fn();
    Object.assign(URL, { createObjectURL, revokeObjectURL });
    const click = vi.fn();
    const origCreate = document.createElement.bind(document);
    vi.spyOn(document, "createElement").mockImplementation((tag: string) => {
      const el = origCreate(tag);
      if (tag === "a") el.click = click as unknown as () => void;
      return el;
    });

    render(SubmissionsPage);

    expect(await screen.findByText("Ahmad Siswa")).toBeTruthy();

    const exportBtn = screen.getByRole("button", { name: /Ekspor CSV/i });
    await fireEvent.click(exportBtn);

    expect(createObjectURL).toHaveBeenCalled();
    expect(click).toHaveBeenCalled();
    vi.restoreAllMocks();
  });
});
