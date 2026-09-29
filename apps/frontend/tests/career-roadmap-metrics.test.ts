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

  it("loads the counselor pending queue once auth resolves after mount", async () => {
    // Hard refresh: the page mounts while auth is still loading, so the caller's
    // role is unknown. A counselor's pending-review queue must still load once
    // auth settles (previously it was fetched once, before the role was known).
    const counselor = { ...student, id: "t1", roles: ["teacher"] };
    let resolveMe: (u: unknown) => void = () => {};
    const mePromise = new Promise((res) => {
      resolveMe = res;
    });
    get.mockImplementation((path: string) => {
      if (path.includes("/auth/me")) return mePromise;
      if (path.startsWith("/career/recommendations/pending"))
        return Promise.resolve([
          {
            id: "pr1",
            user_id: "s9",
            display_name: "Budi Calon",
            major: "Kedokteran",
            created_at: "2026-01-01T00:00:00Z",
          },
        ]);
      if (path.startsWith("/career/recommendations")) return Promise.resolve([]);
      if (path.startsWith("/career/roadmap")) return Promise.resolve(milestones);
      return Promise.resolve([]);
    });

    const loading = auth.load();
    render(RoadmapPage);
    // Page mounts in the loading state (auth unresolved); it must not have
    // fetched the counselor-only queue yet.
    expect(
      get.mock.calls.some((c) => String(c[0]).includes("/career/recommendations/pending")),
    ).toBe(false);

    // Auth resolves to the counselor.
    resolveMe(counselor);
    await loading;

    // The pending queue is fetched once the role is known.
    await waitFor(() =>
      expect(
        get.mock.calls.some((c) => String(c[0]).includes("/career/recommendations/pending")),
      ).toBe(true),
    );
    expect(await screen.findByText("Budi Calon")).toBeTruthy();
  });
});
