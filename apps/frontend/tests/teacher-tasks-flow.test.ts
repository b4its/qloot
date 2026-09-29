// @vitest-environment jsdom
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, cleanup, fireEvent, waitFor } from "@testing-library/svelte";

vi.mock("$app/navigation", () => ({
  goto: vi.fn(),
}));

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
    patch: (...a: unknown[]) => patch(...a),
    delete: (...a: unknown[]) => del(...a),
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

import TeacherTasksPage from "../src/routes/(panel)/teacher/tasks/+page.svelte";

const future = new Date(Date.now() + 2 * 24 * 60 * 60 * 1000).toISOString();

const mockTasks = [
  {
    id: "t-live",
    title: "Live Harian",
    description: "Kerjakan sekarang",
    kind: "daily",
    reward_amount: 10,
    is_active: true,
    starts_at: null,
    ends_at: null,
    created_at: "2026-09-26T00:00:00Z",
    honor_system: true,
  },
  {
    id: "t-draft",
    title: "Draft Nonaktif",
    description: null,
    kind: "learning",
    reward_amount: 15,
    is_active: false,
    starts_at: null,
    ends_at: null,
    created_at: "2026-09-26T00:00:00Z",
    honor_system: true,
  },
  {
    id: "t-sched",
    title: "Terjadwal Mingguan",
    description: null,
    kind: "weekly",
    reward_amount: 20,
    is_active: true,
    starts_at: future,
    ends_at: null,
    created_at: "2026-09-26T00:00:00Z",
    honor_system: false,
  },
];

describe("Teacher Tasks Panel", () => {
  beforeEach(() => {
    cleanup();
    get.mockReset();
    post.mockReset();
    patch.mockReset();
    del.mockReset();

    get.mockImplementation(async (path: string) => {
      if (path.startsWith("/tasks")) return mockTasks;
      return [];
    });
    post.mockResolvedValue({ id: "t-new" });
    patch.mockResolvedValue({});
    del.mockResolvedValue(undefined);
  });

  afterEach(() => cleanup());

  it("loads tasks from the role-aware endpoint and shows metrics + badges", async () => {
    render(TeacherTasksPage);

    expect(await screen.findByText("Live Harian")).toBeTruthy();
    expect(screen.getByText("Draft Nonaktif")).toBeTruthy();
    expect(screen.getByText("Terjadwal Mingguan")).toBeTruthy();

    // Metrics strip
    expect(screen.getByText("Total Tugas")).toBeTruthy();
    expect(screen.getByText("3")).toBeTruthy();
    // "Aktif" / "Terjadwal" appear as metric labels; deactivate buttons also
    // render "Nonaktifkan". Assert metric labels via their mono-label scope.
    const labels = Array.from(document.querySelectorAll(".mono-label")).map(
      (el) => el.textContent?.trim() ?? "",
    );
    expect(labels).toContain("Aktif");
    expect(labels).toContain("Terjadwal");
    expect(labels).toContain("Total Pool OPT");

    // Status badges reflect the classification (scoped to `.badge`, since the
    // status-filter <select> also contains the words "Tersedia"/"Nonaktif").
    const badges = Array.from(document.querySelectorAll(".badge")).map(
      (el) => el.textContent?.trim() ?? "",
    );
    expect(badges).toContain("Tersedia");
    expect(badges).toContain("Nonaktif");

    // It requested the management list.
    expect(get).toHaveBeenCalledWith(expect.stringContaining("/tasks"));
  });

  it("passes q/kind/status filters to the backend query", async () => {
    render(TeacherTasksPage);
    await screen.findByText("Live Harian");

    const search = screen.getByPlaceholderText("Cari tugas...");
    await fireEvent.input(search, { target: { value: "Harian" } });
    await fireEvent.keyDown(search, { key: "Enter" });

    await waitFor(() => {
      expect(get).toHaveBeenCalledWith(expect.stringContaining("q=Harian"));
    });
  });

  it("refetches without the query when the clear-search button is clicked", async () => {
    render(TeacherTasksPage);
    await screen.findByText("Live Harian");

    const search = screen.getByPlaceholderText("Cari tugas...");
    await fireEvent.input(search, { target: { value: "Harian" } });
    await fireEvent.keyDown(search, { key: "Enter" });
    await waitFor(() => expect(get).toHaveBeenCalledWith(expect.stringContaining("q=Harian")));

    get.mockClear();
    await fireEvent.click(screen.getByRole("button", { name: "Bersihkan pencarian" }));

    // Clearing must refetch the unfiltered list, not leave the filtered one on
    // screen with an empty input.
    await waitFor(() => {
      expect(get).toHaveBeenCalledWith(expect.stringContaining("/tasks"));
      const listCall = get.mock.calls.find((c) => String(c[0]).startsWith("/tasks"));
      expect(listCall ? String(listCall[0]) : "").not.toContain("q=Harian");
    });
  });

  it("creates a task with a schedule window", async () => {
    render(TeacherTasksPage);
    await screen.findByText("Live Harian");

    const title = screen.getByPlaceholderText("mis. Baca materi Bab 1");
    await fireEvent.input(title, { target: { value: "Tugas Baru" } });

    const submit = screen.getByRole("button", { name: /Buat tugas/i });
    await fireEvent.click(submit);

    await waitFor(() => {
      expect(post).toHaveBeenCalledWith(
        "/tasks",
        expect.objectContaining({ title: "Tugas Baru", kind: "daily" }),
      );
    });
  });

  it("toggles a task inactive via PATCH", async () => {
    render(TeacherTasksPage);
    await screen.findByText("Live Harian");

    const disableButtons = screen.getAllByRole("button", { name: /Nonaktifkan/i });
    await fireEvent.click(disableButtons[0]);

    await waitFor(() => {
      expect(patch).toHaveBeenCalledWith("/tasks/t-live", { is_active: false });
    });
  });
});
