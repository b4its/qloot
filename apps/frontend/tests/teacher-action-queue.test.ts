// @vitest-environment jsdom
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, cleanup, waitFor } from "@testing-library/svelte";

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
vi.mock("$app/navigation", () => ({ goto: vi.fn() }));

import TeacherHub from "$routes-panel/teacher/+page.svelte";
import { auth } from "../src/lib/stores/auth";

const teacher = {
  id: "t-1",
  email: "t@x.com",
  full_name: "Budi Guru",
  is_active: true,
  chain_user_ref: "0x0",
  created_at: "2026-01-01T00:00:00Z",
  roles: ["teacher"],
};

describe("teacher hub — action queue (W3)", () => {
  beforeEach(() => {
    cleanup();
    get.mockReset();
    auth.setUser(teacher);
  });
  afterEach(() => auth.setUser(null));

  it("renders the aggregated action queue from analytics", async () => {
    get.mockImplementation((path: string) => {
      if (path === "/teacher/analytics")
        return Promise.resolve({
          exams: 3,
          graded_attempts: 10,
          average_score_bp: 7500,
          pass_rate_bp: 8000,
          quests: 2,
          winners: 4,
          opc_awarded: 120,
          actions: [
            {
              kind: "grading_failed",
              count: 2,
              href: "/teacher/submissions?status=ungraded",
              label: "Penilaian gagal / perlu dinilai ulang",
              severity: "urgent",
            },
            {
              kind: "question_review",
              count: 5,
              href: "/teacher/materials",
              label: "Draf soal menunggu tinjauan",
              severity: "warning",
            },
          ],
        });
      return Promise.resolve([]);
    });

    render(TeacherHub);
    await waitFor(() =>
      expect(document.querySelector('[data-role="teacher-action-queue"]')).toBeTruthy(),
    );
    expect(screen.getByText("Penilaian gagal / perlu dinilai ulang")).toBeTruthy();
    expect(screen.getByText("Draf soal menunggu tinjauan")).toBeTruthy();
    const link = screen.getByText("Draf soal menunggu tinjauan").closest("a");
    expect(link?.getAttribute("href")).toBe("/teacher/materials");
  });

  it("shows an all-clear state when nothing needs action", async () => {
    get.mockImplementation((path: string) => {
      if (path === "/teacher/analytics")
        return Promise.resolve({
          exams: 0,
          graded_attempts: 0,
          average_score_bp: 0,
          pass_rate_bp: 0,
          quests: 0,
          winners: 0,
          opc_awarded: 0,
          actions: [],
        });
      return Promise.resolve([]);
    });

    render(TeacherHub);
    await waitFor(() => expect(screen.getByText(/tidak ada antrean mendesak/i)).toBeTruthy());
  });
});
