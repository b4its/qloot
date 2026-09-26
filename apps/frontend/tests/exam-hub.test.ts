// @vitest-environment jsdom
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, fireEvent, cleanup, waitFor } from "@testing-library/svelte";

vi.mock("$app/stores", () => ({
  page: {
    subscribe: (fn: (v: unknown) => void) => (
      fn({ params: {}, url: new URL("http://x/exams") }),
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

import ExamsPage from "$routes-site/exams/+page.svelte";
import { auth } from "../src/lib/stores/auth";

const future = new Date(Date.now() + 7 * 864e5).toISOString();
const past = new Date(Date.now() - 7 * 864e5).toISOString();

const exams = [
  {
    id: "e-open",
    title: "Kuis Terbuka",
    owner_id: "t1",
    duration_minutes: 15,
    status: "published",
    is_active: true,
    passing_score_bp: 6000,
    max_attempts: 2,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    question_count: 5,
    mc_count: 5,
    essay_count: 0,
  },
  {
    id: "e-upcoming",
    title: "Ujian Akan Datang",
    owner_id: "t1",
    duration_minutes: 45,
    status: "published",
    is_active: true,
    passing_score_bp: 6000,
    opens_at: future,
    created_at: "2026-01-02T00:00:00Z",
    updated_at: "2026-01-02T00:00:00Z",
    question_count: 3,
    mc_count: 0,
    essay_count: 3,
  },
  {
    id: "e-closed",
    title: "Ujian Ditutup",
    owner_id: "t1",
    duration_minutes: 30,
    status: "closed",
    is_active: false,
    passing_score_bp: 6000,
    closes_at: past,
    created_at: "2026-01-03T00:00:00Z",
    updated_at: "2026-01-03T00:00:00Z",
    question_count: 4,
    mc_count: 2,
    essay_count: 2,
  },
];

const attempts = [
  {
    id: "a1",
    exam_id: "e-open",
    user_id: "u1",
    attempt_number: 1,
    status: "graded",
    score_bp: 8500,
    passed: true,
    started_at: "2026-01-04T00:00:00Z",
    submitted_at: "2026-01-04T00:10:00Z",
    graded_at: "2026-01-04T00:11:00Z",
  },
];

describe("student exams page — hub UX", () => {
  beforeEach(() => {
    cleanup();
    get.mockReset();
    auth.setUser({
      id: "u1",
      email: "s@x.com",
      full_name: "Student",
      is_active: true,
      chain_user_ref: "0x0",
      created_at: "2026-01-01T00:00:00Z",
      roles: ["student"],
    });
    get.mockImplementation((path: string) => {
      if (path.startsWith("/attempts")) return Promise.resolve(attempts);
      if (path.startsWith("/exams")) return Promise.resolve(exams);
      return Promise.resolve([]);
    });
  });
  afterEach(() => auth.setUser(null));

  it("shows overview metrics including the open count", async () => {
    render(ExamsPage);
    await waitFor(() => expect(screen.getByText("Kuis Terbuka")).toBeTruthy());
    expect(document.querySelector('[data-role="open-count"]')?.textContent?.trim()).toBe("1");
  });

  it("surfaces each exam's attempt status and best score", async () => {
    render(ExamsPage);
    await waitFor(() => expect(screen.getByText("Kuis Terbuka")).toBeTruthy());
    expect(screen.getByText("Skor terbaik 85%")).toBeTruthy();
    // Only the two exams without a completed attempt show the "start" affordance.
    expect(screen.getAllByText("Kerjakan sekarang").length).toBe(2);
  });

  it("filters by availability status", async () => {
    render(ExamsPage);
    await waitFor(() => expect(screen.getByText("Kuis Terbuka")).toBeTruthy());

    // The status filter button is a plain button; the card chip is a span.
    const upcomingBtn = screen
      .getAllByRole("button", { name: "Akan datang" })
      .find((b) => b.classList.contains("rounded-xs"));
    await fireEvent.click(upcomingBtn!);
    await waitFor(() => expect(screen.queryByText("Kuis Terbuka")).toBeNull());
    expect(screen.getByText("Ujian Akan Datang")).toBeTruthy();
  });

  it("searches exams by title", async () => {
    render(ExamsPage);
    await waitFor(() => expect(screen.getByText("Kuis Terbuka")).toBeTruthy());

    const input = screen.getByLabelText("Cari ujian") as HTMLInputElement;
    await fireEvent.input(input, { target: { value: "ditutup" } });
    await waitFor(() => expect(screen.queryByText("Kuis Terbuka")).toBeNull());
    expect(screen.getByText("Ujian Ditutup")).toBeTruthy();
  });

  it("classifies availability by the window (open/upcoming/closed)", async () => {
    render(ExamsPage);
    await waitFor(() => expect(screen.getByText("Kuis Terbuka")).toBeTruthy());
    expect(document.querySelector('[data-exam="e-open"]')?.getAttribute("data-status")).toBe(
      "open",
    );
    expect(document.querySelector('[data-exam="e-upcoming"]')?.getAttribute("data-status")).toBe(
      "upcoming",
    );
    expect(document.querySelector('[data-exam="e-closed"]')?.getAttribute("data-status")).toBe(
      "closed",
    );
  });
});
