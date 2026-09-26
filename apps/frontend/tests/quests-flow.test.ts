// @vitest-environment jsdom
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, cleanup, fireEvent, waitFor } from "@testing-library/svelte";

const get = vi.fn();
const post = vi.fn();

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

vi.mock("../src/lib/stores/auth", () => ({
  auth: {
    subscribe: (fn: (v: unknown) => void) => {
      fn({
        user: { id: "u-teacher-1", email: "teacher@test.com", role: "teacher" },
        loading: false,
      });
      return () => {};
    },
  },
  hasRole: (user: { role?: string } | null, role: string) => user?.role === role,
}));

import QuestsPage from "../src/routes/(site)/quests/+page.svelte";

const mockQuests = [
  {
    id: "q-1",
    title: "Tantangan Algoritma Graf",
    description: "Selesaikan ujian Dijkstra dan Floyd-Warshall secepat mungkin.",
    status: "open",
    top_n_winners: 3,
    rules: [
      { rank: 1, reward_amount: 150 },
      { rank: 2, reward_amount: 100 },
      { rank: 3, reward_amount: 50 },
    ],
  },
  {
    id: "q-2",
    title: "Tantangan Basis Data Terdistribusi",
    description: "Ujian transaksi ACID dan sharding.",
    status: "finalized",
    top_n_winners: 2,
    rules: [
      { rank: 1, reward_amount: 200 },
      { rank: 2, reward_amount: 100 },
    ],
  },
];

const mockWinners = [
  {
    rank: 1,
    user_id: "student-12345678",
    score_bp: 9800,
    reward_amount: 200,
  },
];

const mockLeaderboard = {
  scope: "quest",
  scope_id: "q-2",
  entries: [
    {
      rank: 1,
      user_id: "student-12345678",
      score_bp: 9800,
      display_name: "Budi Juara",
      reward_amount: 200,
      reward_status: "confirmed",
    },
  ],
};

describe("Quests Flow UI/UX Enhancements", () => {
  beforeEach(() => {
    cleanup();
    get.mockReset();
    post.mockReset();

    get.mockImplementation(async (path: string) => {
      if (path.startsWith("/quests/q-2/winners")) return mockWinners;
      if (path.startsWith("/rankings/quests/q-2")) return mockLeaderboard;
      if (path.startsWith("/quests")) return mockQuests;
      return [];
    });
    post.mockResolvedValue({ allocations_created: 1 });
  });

  afterEach(() => cleanup());

  it("renders quests with metrics overview, reward rules, and winner badges", async () => {
    render(QuestsPage);

    expect(await screen.findByText("Tantangan Algoritma Graf")).toBeTruthy();
    expect(screen.getByText("Tantangan Basis Data Terdistribusi")).toBeTruthy();

    // Check summary metrics
    expect(screen.getByText("Total Quest")).toBeTruthy();
    expect(screen.getByText("Quest Aktif")).toBeTruthy();
    expect(screen.getByText("Total Pool Hadiah")).toBeTruthy();
    expect(screen.getByText("600 OPT")).toBeTruthy(); // 150+100+50 + 200+100 = 600

    // Check rules breakdown
    expect(screen.getAllByText("Total 300 OPT").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Total 300 OPT").length).toBeGreaterThanOrEqual(1);
  });

  it("filters quests by search query and status tabs", async () => {
    render(QuestsPage);

    expect(await screen.findByText("Tantangan Algoritma Graf")).toBeTruthy();

    // Filter by search query
    const searchInput = screen.getByPlaceholderText("Cari judul quest...");
    await fireEvent.input(searchInput, { target: { value: "Basis Data" } });

    expect(screen.queryByText("Tantangan Algoritma Graf")).toBeNull();
    expect(screen.getByText("Tantangan Basis Data Terdistribusi")).toBeTruthy();

    // Clear search
    await fireEvent.input(searchInput, { target: { value: "" } });
    expect(screen.getByText("Tantangan Algoritma Graf")).toBeTruthy();

    // Filter by Aktif (open)
    const activeTab = screen.getByRole("button", { name: "Aktif" });
    await fireEvent.click(activeTab);

    expect(screen.getByText("Tantangan Algoritma Graf")).toBeTruthy();
    expect(screen.queryByText("Tantangan Basis Data Terdistribusi")).toBeNull();
  });

  it("opens and dismisses quest leaderboard modal", async () => {
    render(QuestsPage);

    expect(await screen.findByText("Tantangan Basis Data Terdistribusi")).toBeTruthy();

    const leaderboardBtn = screen.getByRole("button", { name: /Papan Peringkat Quest/i });
    await fireEvent.click(leaderboardBtn);

    expect(await screen.findByText("Budi Juara")).toBeTruthy();
    expect(screen.getByText("confirmed")).toBeTruthy();

    // Close modal
    const closeBtns = screen.getAllByRole("button", { name: "Tutup" });
    await fireEvent.click(closeBtns[0]);

    expect(screen.queryByText("Budi Juara")).toBeNull();
  });

  it("opens finalization confirmation modal and executes finalize on confirm", async () => {
    render(QuestsPage);

    expect(await screen.findByText("Tantangan Algoritma Graf")).toBeTruthy();

    const finalizeBtn = screen.getByRole("button", { name: "Finalisasi pemenang" });
    await fireEvent.click(finalizeBtn);

    // Modal appeared
    expect(screen.getByText("Konfirmasi Finalisasi Quest")).toBeTruthy();

    // Click confirm in modal
    const confirmBtn = screen.getByRole("button", { name: "Ya, Finalisasi Pemenang" });
    await fireEvent.click(confirmBtn);

    expect(post).toHaveBeenCalledWith("/quests/q-1/finalize");
    expect(screen.queryByText("Konfirmasi Finalisasi Quest")).toBeNull();
  });
});
