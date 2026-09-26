// @vitest-environment jsdom
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, fireEvent, cleanup, waitFor } from "@testing-library/svelte";

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

import TeacherExams from "$routes-panel/teacher/exams/+page.svelte";
import { auth } from "../src/lib/stores/auth";

const teacher = {
  id: "t1",
  email: "t@x.com",
  full_name: "Teacher",
  is_active: true,
  chain_user_ref: "0x0",
  created_at: "2026-01-01T00:00:00Z",
  roles: ["teacher"],
};

const exams = [
  {
    id: "e1",
    title: "Kuis PG Aktif",
    owner_id: "t1",
    duration_minutes: 15,
    status: "published",
    is_active: true,
    passing_score_bp: 6000,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    question_count: 5,
    mc_count: 5,
    essay_count: 0,
  },
  {
    id: "e2",
    title: "Esai Draf",
    owner_id: "t1",
    duration_minutes: 60,
    status: "draft",
    is_active: false,
    passing_score_bp: 6000,
    created_at: "2026-01-02T00:00:00Z",
    updated_at: "2026-01-02T00:00:00Z",
    question_count: 3,
    mc_count: 0,
    essay_count: 3,
  },
];

describe("teacher exams — metrics, search, and status filter", () => {
  beforeEach(() => {
    cleanup();
    get.mockReset();
    auth.setUser(teacher);
    get.mockImplementation((path: string) =>
      path.startsWith("/exams") ? Promise.resolve(exams) : Promise.resolve([]),
    );
  });
  afterEach(() => auth.setUser(null));

  it("renders the exam metrics", async () => {
    render(TeacherExams);
    await waitFor(() => expect(screen.getByText("Kuis PG Aktif")).toBeTruthy());
    expect(document.querySelector('[data-role="active-count"]')?.textContent?.trim()).toBe("1");
    // 5 + 3 = 8 total questions.
    expect(screen.getByText("8")).toBeTruthy();
  });

  it("filters to drafts", async () => {
    render(TeacherExams);
    await waitFor(() => expect(screen.getByText("Kuis PG Aktif")).toBeTruthy());

    await fireEvent.click(screen.getByRole("button", { name: "Draf" }));
    await waitFor(() => expect(screen.queryByText("Kuis PG Aktif")).toBeNull());
    expect(screen.getByText("Esai Draf")).toBeTruthy();
  });

  it("searches exams by title", async () => {
    render(TeacherExams);
    await waitFor(() => expect(screen.getByText("Kuis PG Aktif")).toBeTruthy());

    const input = screen.getByLabelText("Cari ujian") as HTMLInputElement;
    await fireEvent.input(input, { target: { value: "esai" } });
    await waitFor(() => expect(screen.queryByText("Kuis PG Aktif")).toBeNull());
    expect(screen.getByText("Esai Draf")).toBeTruthy();
  });

  it("combines a category tab with the status filter", async () => {
    render(TeacherExams);
    await waitFor(() => expect(screen.getByText("Kuis PG Aktif")).toBeTruthy());

    await fireEvent.click(screen.getByRole("tab", { name: /esai/i }));
    await waitFor(() => expect(screen.queryByText("Kuis PG Aktif")).toBeNull());
    expect(screen.getByText("Esai Draf")).toBeTruthy();
  });
});
