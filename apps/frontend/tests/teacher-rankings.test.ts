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

import TeacherRankings from "$routes-panel/teacher/rankings/+page.svelte";
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

const page1 = {
  scope: "global",
  period: "all",
  entries: [
    { user_id: "u1", rank: 1, score_bp: 9200, opc_earned: 120, display_name: "Andi" },
    { user_id: "u2", rank: 2, score_bp: 5500, opc_earned: 80, display_name: "Bunga" },
    { user_id: "u3", rank: 3, score_bp: 7000, opc_earned: 60, display_name: "Cinta" },
  ],
};

describe("teacher rankings — period, search, sort, and metrics", () => {
  beforeEach(() => {
    cleanup();
    get.mockReset();
    auth.setUser(teacher);
    get.mockImplementation((path: string) => {
      if (path.startsWith("/rankings/global")) return Promise.resolve(page1);
      return Promise.resolve([]);
    });
  });
  afterEach(() => auth.setUser(null));

  it("renders the page-level metric strip", async () => {
    render(TeacherRankings);
    await waitFor(() => expect(screen.getByText("Andi")).toBeTruthy());
    // Top 92.0%, avg (92+55+70)/3 = 72.3%, one passing (>=60).
    expect(document.querySelector('[data-role="top-score"]')?.textContent?.trim()).toBe("92.0%");
    expect(document.querySelector('[data-role="avg-score"]')?.textContent?.trim()).toBe("72.3%");
  });

  it("requests a different period when a tab is clicked", async () => {
    render(TeacherRankings);
    await waitFor(() => expect(screen.getByText("Andi")).toBeTruthy());

    await fireEvent.click(screen.getByRole("tab", { name: "Minggu ini" }));
    await waitFor(() =>
      expect(get.mock.calls.some((c) => String(c[0]).includes("period=weekly"))).toBe(true),
    );
  });

  it("filters entries by student name", async () => {
    render(TeacherRankings);
    await waitFor(() => expect(screen.getByText("Andi")).toBeTruthy());

    const input = screen.getByLabelText("Cari siswa") as HTMLInputElement;
    await fireEvent.input(input, { target: { value: "bunga" } });
    await waitFor(() => expect(screen.queryByText("Andi")).toBeNull());
    expect(screen.getByText("Bunga")).toBeTruthy();
  });

  it("sorts by OPT descending", async () => {
    render(TeacherRankings);
    await waitFor(() => expect(screen.getByText("Andi")).toBeTruthy());

    const select = screen.getByLabelText("Urutkan") as HTMLSelectElement;
    await fireEvent.change(select, { target: { value: "opc" } });
    await waitFor(() => {
      const rows = Array.from(document.querySelectorAll("tbody tr td:nth-child(2)")).map((td) =>
        td.textContent?.trim(),
      );
      // Andi (120) > Bunga (80) > Cinta (60).
      expect(rows[0]).toBe("Andi");
      expect(rows[2]).toBe("Cinta");
    });
  });
});
