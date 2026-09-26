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

import CareerHub from "$routes-site/career/+page.svelte";

function routes(map: Record<string, unknown>) {
  get.mockImplementation((path: string) => {
    for (const [prefix, value] of Object.entries(map)) {
      if (path.startsWith(prefix)) return Promise.resolve(value);
    }
    return Promise.resolve([]);
  });
}

describe("career hub — status-aware modules", () => {
  beforeEach(() => {
    cleanup();
    get.mockReset();
  });
  afterEach(() => cleanup());

  it("shows live module status from the loaded endpoints", async () => {
    routes({
      "/career/grades": [{ id: "g1", subject: "Fisika", grade: 90, term: "2025/2026" }],
      "/career/personality": {
        openness: 80,
        conscientiousness: 70,
        extraversion: 60,
        agreeableness: 75,
        neuroticism: 30,
        created_at: "2026-01-01T00:00:00Z",
      },
      "/career/recommendations": [{ id: "r1", major: "Teknik", fit_score: 90, status: "approved" }],
      "/career/roadmap": [
        {
          id: "m1",
          title: "Tahap 1",
          period: "2026",
          position: 0,
          progress_percent: 100,
          status: "done",
        },
        {
          id: "m2",
          title: "Tahap 2",
          period: "2026",
          position: 1,
          progress_percent: 0,
          status: "todo",
        },
      ],
      "/career/consultations": [
        {
          id: "c1",
          counselor: "Bu Rina",
          topic: "Jurusan",
          status: "scheduled",
          created_at: "2026-01-01T00:00:00Z",
        },
      ],
    });
    render(CareerHub);

    await waitFor(() =>
      expect(screen.getByText("Rencanakan masa depanmu dengan data")).toBeTruthy(),
    );
    // Grades loaded → "1 nilai"; personality filled; roadmap half done (50%).
    await waitFor(() => expect(screen.getByText("1 nilai")).toBeTruthy());
    expect(screen.getByText("Sudah diisi")).toBeTruthy();
    expect(document.querySelector('[data-role="roadmap-pct"]')?.textContent?.trim()).toBe("50%");
    expect(screen.getByText("1 jadwal aktif")).toBeTruthy();
  });

  it("shows neutral status when a module has no data yet", async () => {
    routes({
      "/career/grades": [],
      "/career/personality": null,
      "/career/recommendations": [],
      "/career/roadmap": [],
      "/career/consultations": [],
    });
    render(CareerHub);

    await waitFor(() => expect(screen.getByText("Belum ada nilai")).toBeTruthy());
    expect(screen.getByText("Belum diisi")).toBeTruthy();
    expect(screen.getByText("Belum dibuat")).toBeTruthy();
    expect(screen.getByText("Belum ada sesi")).toBeTruthy();
  });

  it("computes a readiness percentage across the four data modules", async () => {
    // Only grades + personality are set → 2/4 = 50%.
    routes({
      "/career/grades": [{ id: "g1", subject: "Fisika", grade: 90, term: "2025/2026" }],
      "/career/personality": {
        openness: 80,
        conscientiousness: 70,
        extraversion: 60,
        agreeableness: 75,
        neuroticism: 30,
        created_at: "2026-01-01T00:00:00Z",
      },
      "/career/recommendations": [],
      "/career/roadmap": [],
      "/career/consultations": [],
    });
    render(CareerHub);
    await waitFor(() =>
      expect(document.querySelector('[data-role="readiness"]')?.textContent?.trim()).toBe("50%"),
    );
  });
});
