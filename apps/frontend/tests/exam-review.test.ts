// @vitest-environment jsdom
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/svelte";

// Configurable page store (with the exam id in params).
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
    url: new URL("http://localhost:3000/teacher/exams/e1/results"),
    params: { id: "e1" },
    route: { id: "/teacher/exams/[id]/results" },
    status: 200,
    error: null,
    data: {},
    state: {},
  });
  return { pageStore: store };
});
vi.mock("$app/stores", () => ({ page: pageStore, navigating: { subscribe: () => () => {} } }));
vi.mock("$app/navigation", () => ({ goto: vi.fn() }));

const reviewPayload = {
  exam: { id: "e1", title: "Kuis PG", owner_id: "t1", duration_minutes: 15, status: "published" },
  results: [
    {
      id: "a1",
      exam_id: "e1",
      user_id: "s1",
      attempt_number: 1,
      status: "graded",
      score_bp: 10000,
      passed: true,
      started_at: "2026-01-01T00:00:00Z",
      submitted_at: "2026-01-01T00:10:00Z",
      graded_at: "2026-01-01T00:10:01Z",
      display_name: "Andi Benar",
      answers: [
        {
          question_id: "q1",
          position: 0,
          qtype: "multiple_choice",
          prompt: "Ibu kota Indonesia?",
          answer_text: "A",
          answer_display: "Jakarta",
          correct_answer: "A",
          correct_display: "Jakarta",
          is_correct: true,
          score_bp: 10000,
          max_score_bp: 10000,
          feedback: "Benar",
        },
      ],
    },
    {
      id: "a2",
      exam_id: "e1",
      user_id: "s2",
      attempt_number: 1,
      status: "graded",
      score_bp: 0,
      passed: false,
      started_at: "2026-01-01T00:00:00Z",
      submitted_at: "2026-01-01T00:10:00Z",
      graded_at: "2026-01-01T00:10:01Z",
      display_name: "Budi Salah",
      answers: [
        {
          question_id: "q1",
          position: 0,
          qtype: "multiple_choice",
          prompt: "Ibu kota Indonesia?",
          answer_text: "B",
          answer_display: "Bandung",
          correct_answer: "A",
          correct_display: "Jakarta",
          is_correct: false,
          score_bp: 0,
          max_score_bp: 10000,
          feedback: "Salah",
        },
      ],
    },
  ],
};

vi.mock("../src/lib/api/client", () => ({
  API_BASE: "http://localhost:8000",
  ApiError: class ApiError extends Error {
    status = 0;
  },
  api: { get: vi.fn(), post: vi.fn(), put: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}));

import { api } from "$lib/api/client";
import { auth } from "$lib/stores/auth";
import ResultsPage from "../src/routes/(panel)/teacher/exams/[id]/results/+page.svelte";

const teacher = {
  id: "t1",
  email: "t@x.com",
  full_name: "Teacher",
  is_active: true,
  chain_user_ref: "0x0",
  created_at: new Date().toISOString(),
  roles: ["teacher"],
};

describe("teacher exam results review", () => {
  beforeEach(() => {
    cleanup();
    auth.setUser(teacher);
    (api.get as unknown as ReturnType<typeof vi.fn>).mockImplementation((path: string) =>
      path.includes("/results/review")
        ? Promise.resolve(reviewPayload)
        : Promise.resolve(reviewPayload.exam),
    );
  });
  afterEach(() => auth.setUser(null));

  it("lists each student who attempted the exam", async () => {
    render(ResultsPage, {});
    expect(await screen.findByText("Andi Benar")).toBeTruthy();
    expect(await screen.findByText("Budi Salah")).toBeTruthy();
  });

  it("expands a student to show questions, answers and correctness", async () => {
    render(ResultsPage, {});
    // Expand the correct student's sheet.
    await fireEvent.click(await screen.findByText("Andi Benar"));
    // Question prompt + resolved chosen option text.
    expect(await screen.findByText("Ibu kota Indonesia?")).toBeTruthy();
    expect(screen.getByText("Jakarta")).toBeTruthy();
    // Correctness badge.
    expect(screen.getAllByText("Benar").length).toBeGreaterThan(0);
  });

  it("shows the correct option text for a wrong answer", async () => {
    render(ResultsPage, {});
    await fireEvent.click(await screen.findByText("Budi Salah"));
    // Chosen (wrong) option text + the correct key.
    expect(await screen.findByText("Bandung")).toBeTruthy();
    // "Salah" badge appears for the wrong answer.
    expect(screen.getAllByText("Salah").length).toBeGreaterThan(0);
    // The key text is shown too.
    expect(screen.getAllByText(/Jakarta/).length).toBeGreaterThan(0);
  });

  it("offers a per-answer override control on a graded sheet", async () => {
    render(ResultsPage, {});
    await fireEvent.click(await screen.findByText("Andi Benar"));
    expect(await screen.findByText("Override nilai (%)")).toBeTruthy();
    expect(screen.getAllByRole("button", { name: /simpan/i }).length).toBeGreaterThan(0);
  });

  it("calls the override endpoint when saving a score", async () => {
    const post = api.post as unknown as ReturnType<typeof vi.fn>;
    post.mockResolvedValue({});
    render(ResultsPage, {});
    await fireEvent.click(await screen.findByText("Andi Benar"));
    const save = (await screen.findAllByRole("button", { name: /simpan/i }))[0];
    await fireEvent.click(save);
    expect(post).toHaveBeenCalledWith(
      expect.stringContaining("/override"),
      expect.objectContaining({ score_bp: expect.any(Number) }),
    );
  });
});
