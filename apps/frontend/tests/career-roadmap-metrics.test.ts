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

import RoadmapPage from "$routes-site/career/roadmap/+page.svelte";
import { auth } from "../src/lib/stores/auth";

const student = {
  id: "u1",
  email: "s@x.com",
  full_name: "Student",
  is_active: true,
  chain_user_ref: "0x0",
  created_at: "2026-01-01T00:00:00Z",
  roles: ["student"],
};

const milestones = [
  {
    id: "m1",
    title: "Tahap 1",
    description: "mulai",
    period: "2026",
    position: 0,
    progress_percent: 100,
    status: "completed",
    tasks: [
      { title: "Tugas A", done: true },
      { title: "Tugas B", done: true },
    ],
  },
  {
    id: "m2",
    title: "Tahap 2",
    description: "lanjut",
    period: "2026",
    position: 1,
    progress_percent: 50,
    status: "in_progress",
    tasks: [
      { title: "Tugas C", done: true },
      { title: "Tugas D", done: false },
    ],
  },
];

describe("career roadmap — progress metrics", () => {
  beforeEach(() => {
    cleanup();
    get.mockReset();
    auth.setUser(student);
    get.mockImplementation((path: string) => {
      if (path.startsWith("/career/recommendations"))
        return Promise.resolve([
          {
            id: "r1",
            major: "Teknik Informatika",
            fit_score: 90,
            academic_fit: 88,
            personality_fit: 92,
            rank: 1,
            status: "approved",
          },
        ]);
      if (path.startsWith("/career/roadmap")) return Promise.resolve(milestones);
      return Promise.resolve([]);
    });
  });
  afterEach(() => auth.setUser(null));

  it("shows milestone and task metrics", async () => {
    render(RoadmapPage);
    await waitFor(() => expect(screen.getByText("Tahap 1")).toBeTruthy());
    expect(document.querySelector('[data-role="completed-milestones"]')?.textContent?.trim()).toBe(
      "1",
    );
    // Roadmap avg = (100 + 50) / 2 = 75%.
    expect(document.querySelector('[data-role="roadmap-pct"]')?.textContent?.trim()).toBe("75%");
    // 3 of 4 tasks done.
    expect(document.querySelector('[data-role="task-count"]')?.textContent?.trim()).toBe("3/4");
  });

  it("renders the overall task progress bar", async () => {
    render(RoadmapPage);
    await waitFor(() => expect(screen.getByText("Tahap 1")).toBeTruthy());
    const bar = screen.getByRole("progressbar", { name: "Penyelesaian tugas peta jalan" });
    expect(bar.getAttribute("aria-valuenow")).toBe("3");
    expect(bar.getAttribute("aria-valuemax")).toBe("4");
  });

  it("notes how many milestones are in progress", async () => {
    render(RoadmapPage);
    await waitFor(() => expect(screen.getByText(/1 tonggak sedang berjalan/)).toBeTruthy());
  });
});
