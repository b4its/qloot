// @vitest-environment jsdom
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, cleanup, fireEvent, waitFor } from "@testing-library/svelte";

const get = vi.fn();
const post = vi.fn();
const refreshOpt = vi.fn();

vi.mock("../src/lib/api/client", () => ({
  API_BASE: "http://localhost:8000",
  ApiError: class ApiError extends Error {
    status = 0;
  },
  api: {
    get: (...a: unknown[]) => get(...a),
    post: (...a: unknown[]) => post(...a),
  },
}));

vi.mock("../src/lib/stores/opt", () => ({
  opt: {
    subscribe: (fn: (v: unknown) => void) => {
      fn({ balance: 120, loading: false });
      return () => {};
    },
    refresh: () => refreshOpt(),
  },
}));

vi.mock("../src/lib/actions/reveal", () => ({
  reveal: () => ({ destroy: () => {} }),
}));

import TasksPage from "../src/routes/(site)/tasks/+page.svelte";

const mockTasks = [
  {
    id: "t-1",
    title: "Login Harian Aplikasi",
    description: "Buka platform dan cek misi baru hari ini.",
    kind: "daily",
    reward_amount: 10,
    honor_system: true,
    is_active: true,
    created_at: "2026-09-26T00:00:00Z",
  },
  {
    id: "t-2",
    title: "Pelajari Materi Basis Data",
    description: "Selesaikan modul transaksi relasional.",
    kind: "learning",
    reward_amount: 25,
    honor_system: false,
    is_active: true,
    created_at: "2026-09-26T00:00:00Z",
  },
  {
    id: "t-3",
    title: "Ujian Mingguan Struktur Data",
    description: "Kerjakan tryout mingguan algoritma.",
    kind: "weekly",
    reward_amount: 50,
    honor_system: false,
    is_active: true,
    created_at: "2026-09-26T00:00:00Z",
  },
];

const mockInitialCompletions = [
  {
    id: "comp-1",
    task_id: "t-1",
    user_id: "u-student",
    period_key: "2026-09-26",
    reward_key: "rw-1",
    created_at: "2026-09-26T08:00:00Z",
  },
];

describe("Tasks Page UI/UX Enhancements", () => {
  beforeEach(() => {
    cleanup();
    get.mockReset();
    post.mockReset();
    refreshOpt.mockReset();

    get.mockImplementation(async (path: string) => {
      if (path.startsWith("/tasks/me/completions")) {
        return mockInitialCompletions;
      }
      if (path.startsWith("/tasks")) {
        return mockTasks;
      }
      return [];
    });
    post.mockResolvedValue({ id: "comp-new" });
  });

  afterEach(() => cleanup());

  it("renders tasks list with overview metrics and initial completion state", async () => {
    render(TasksPage);

    expect(await screen.findByText("Login Harian Aplikasi")).toBeTruthy();
    expect(screen.getByText("Pelajari Materi Basis Data")).toBeTruthy();
    expect(screen.getByText("Ujian Mingguan Struktur Data")).toBeTruthy();

    // Check summary metrics
    expect(screen.getByText("Total Tugas")).toBeTruthy();
    expect(screen.getByText("3")).toBeTruthy();
    expect(screen.getByText("Tugas Selesai")).toBeTruthy();
    expect(screen.getByText("1")).toBeTruthy(); // t-1 is completed
    expect(screen.getByText("Tugas Tersedia")).toBeTruthy();
    expect(screen.getByText("2")).toBeTruthy();

    // Check that t-1 shows Selesai badge while t-2 and t-3 show Selesaikan buttons
    const badgeMatches = screen
      .getAllByText("Selesai")
      .filter((el) => el.closest(".badge") !== null);
    expect(badgeMatches.length).toBe(1);
    const completeBtns = screen.getAllByRole("button", { name: /Selesaikan/i });
    expect(completeBtns.length).toBe(2);
  });

  it("filters tasks by search query, kind tabs, and status tabs", async () => {
    render(TasksPage);

    expect(await screen.findByText("Login Harian Aplikasi")).toBeTruthy();

    // Search query filter
    const searchInput = screen.getByPlaceholderText("Cari tugas...");
    await fireEvent.input(searchInput, { target: { value: "Basis Data" } });

    expect(screen.queryByText("Login Harian Aplikasi")).toBeNull();
    expect(screen.getByText("Pelajari Materi Basis Data")).toBeTruthy();

    // Clear search
    await fireEvent.input(searchInput, { target: { value: "" } });
    expect(screen.getByText("Login Harian Aplikasi")).toBeTruthy();

    // Filter by kind: Harian
    const dailyTab = screen.getByRole("button", { name: "Harian" });
    await fireEvent.click(dailyTab);

    expect(screen.getByText("Login Harian Aplikasi")).toBeTruthy();
    expect(screen.queryByText("Pelajari Materi Basis Data")).toBeNull();

    // Reset kind to Semua
    const allKindTab = screen.getByRole("button", { name: "Semua (3)" });
    await fireEvent.click(allKindTab);

    // Filter by status: Selesai
    const doneTab = screen.getByRole("button", { name: "Selesai" });
    await fireEvent.click(doneTab);

    expect(screen.getByText("Login Harian Aplikasi")).toBeTruthy();
    expect(screen.queryByText("Pelajari Materi Basis Data")).toBeNull();
    expect(screen.queryByText("Ujian Mingguan Struktur Data")).toBeNull();
  });

  it("completes a pending task and refreshes OPT store", async () => {
    render(TasksPage);

    expect(await screen.findByText("Pelajari Materi Basis Data")).toBeTruthy();

    const completeBtns = screen.getAllByRole("button", { name: /Selesaikan/i });
    // Click on t-2 Selesaikan
    await fireEvent.click(completeBtns[0]);

    await waitFor(() => {
      expect(post).toHaveBeenCalledWith("/tasks/t-2/complete");
      expect(refreshOpt).toHaveBeenCalled();
      expect(screen.getByText(/Tugas "Pelajari Materi Basis Data" selesai!/i)).toBeTruthy();
    });
  });
});
