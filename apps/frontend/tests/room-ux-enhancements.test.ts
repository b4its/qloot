// @vitest-environment jsdom
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, cleanup, fireEvent, waitFor } from "@testing-library/svelte";

vi.mock("$app/stores", () => ({
  page: {
    subscribe: (fn: (v: unknown) => void) => {
      fn({
        params: { roomId: "r-101" },
        url: new URL("http://localhost:3000/rooms/r-101"),
      });
      return () => {};
    },
  },
}));

const get = vi.fn();
const post = vi.fn();

vi.mock("../src/lib/api/client", () => ({
  API_BASE: "http://localhost:8000",
  wsUrl: (path: string) => `ws://localhost:8000${path}`,
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

import RoomsPage from "../src/routes/(site)/rooms/+page.svelte";
import RoomDetailPage from "../src/routes/(site)/rooms/[roomId]/+page.svelte";

const mockRooms = [
  {
    id: "r-1",
    name: "Ruang Fisika Kuantum",
    code: "FSK101",
    owner_id: "u-teacher-1",
    status: "open",
    max_participants: 50,
    is_public: true,
    is_locked: false,
    created_at: "2026-09-26T08:00:00Z",
  },
  {
    id: "r-2",
    name: "Ruang Matematika Diskrit",
    code: "MTK202",
    owner_id: "u-teacher-1",
    status: "closed",
    max_participants: 30,
    is_public: false,
    is_locked: false,
    created_at: "2026-09-26T08:30:00Z",
  },
  {
    id: "r-3",
    name: "Ruang Kimia Organik",
    code: "KMA303",
    owner_id: "u-teacher-1",
    status: "open",
    max_participants: 100,
    is_public: true,
    is_locked: true,
    created_at: "2026-09-26T09:00:00Z",
  },
];

const mockRoomDetail = {
  id: "r-101",
  name: "Ruang Sains Komputasi",
  code: "SNS999",
  owner_id: "u-teacher-1",
  status: "open",
  max_participants: 80,
  is_public: true,
  is_locked: false,
  created_at: "2026-09-26T08:00:00Z",
};

const mockParticipants = [
  {
    id: "m-1",
    room_id: "r-101",
    user_id: "u-teacher-1",
    role: "teacher",
    is_present: true,
    joined_at: "2026-09-26T08:05:00Z",
    display_name: "Pak Guru Fisika",
  },
  {
    id: "m-2",
    room_id: "r-101",
    user_id: "u-student-1",
    role: "student",
    is_present: true,
    joined_at: "2026-09-26T08:10:00Z",
    display_name: "Andi Siswa",
  },
  {
    id: "m-3",
    room_id: "r-101",
    user_id: "u-student-2",
    role: "student",
    is_present: false,
    joined_at: "2026-09-26T08:15:00Z",
    display_name: "Budi Santoso",
  },
];

const mockLiveBoard = [
  {
    rank: 1,
    user_id: "u-student-1",
    display_name: "Andi Siswa",
    is_present: true,
    score_bp: 9500,
  },
];

const mockRanking = {
  scope: "room",
  scope_id: "r-101",
  entries: [
    {
      user_id: "u-student-1",
      rank: 1,
      score_bp: 9500,
      opc_earned: 50,
      display_name: "Andi Siswa",
    },
  ],
};

describe("Rooms UI/UX Enhancements", () => {
  beforeEach(() => {
    cleanup();
    get.mockReset();
    post.mockReset();

    // Mock WebSocket
    class MockWebSocket {
      onopen: (() => void) | null = null;
      onmessage: ((ev: { data: string }) => void) | null = null;
      onclose: (() => void) | null = null;
      onerror: (() => void) | null = null;
      close = vi.fn();
      send = vi.fn();
      constructor() {
        setTimeout(() => this.onopen?.(), 10);
      }
    }
    (globalThis as unknown as { WebSocket: typeof MockWebSocket }).WebSocket = MockWebSocket;

    get.mockImplementation(async (path: string) => {
      if (path.startsWith("/rooms/r-101/participants")) return mockParticipants;
      if (path.startsWith("/rooms/r-101/live")) return mockLiveBoard;
      if (path.startsWith("/rooms/r-101/events")) return [];
      if (path.startsWith("/rankings/rooms/r-101")) return mockRanking;
      if (path.startsWith("/rooms/r-101")) return mockRoomDetail;
      if (path.startsWith("/rooms")) return mockRooms;
      return [];
    });
  });

  afterEach(() => cleanup());

  it("renders room list with metrics overview and filter controls", async () => {
    render(RoomsPage);

    expect(await screen.findByText("Ruang Fisika Kuantum")).toBeTruthy();
    expect(screen.getByText("Ruang Matematika Diskrit")).toBeTruthy();
    expect(screen.getByText("Ruang Kimia Organik")).toBeTruthy();

    // Overview metrics
    expect(screen.getByText("Total Ruang")).toBeTruthy();
    expect(screen.getByText("Ruang Terbuka")).toBeTruthy();
    expect(screen.getByText("Ruang Terkunci")).toBeTruthy();
    expect(screen.getByText("Ruang Publik")).toBeTruthy();

    // Filter tabs
    expect(screen.getByRole("button", { name: "Semua (3)" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Buka" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Terkunci" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Ditutup" })).toBeTruthy();
  });

  it("filters room list by search query and status filter", async () => {
    render(RoomsPage);

    expect(await screen.findByText("Ruang Fisika Kuantum")).toBeTruthy();

    // Filter by search term
    const searchInput = screen.getByPlaceholderText("Cari nama atau kode ruang...");
    await fireEvent.input(searchInput, { target: { value: "Diskrit" } });

    expect(screen.queryByText("Ruang Fisika Kuantum")).toBeNull();
    expect(screen.getByText("Ruang Matematika Diskrit")).toBeTruthy();

    // Search by code
    await fireEvent.input(searchInput, { target: { value: "FSK101" } });
    expect(screen.getByText("Ruang Fisika Kuantum")).toBeTruthy();
    expect(screen.queryByText("Ruang Matematika Diskrit")).toBeNull();

    // Reset search
    await fireEvent.input(searchInput, { target: { value: "" } });
    expect(screen.getByText("Ruang Fisika Kuantum")).toBeTruthy();

    // Filter by status Terkunci
    const lockedTab = screen.getByRole("button", { name: "Terkunci" });
    await fireEvent.click(lockedTab);

    expect(screen.queryByText("Ruang Fisika Kuantum")).toBeNull();
    expect(screen.queryByText("Ruang Matematika Diskrit")).toBeNull();
    expect(screen.getByText("Ruang Kimia Organik")).toBeTruthy();
  });

  it("copies room code to clipboard when copy button clicked", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, {
      clipboard: { writeText },
    });

    render(RoomsPage);

    expect(await screen.findByText("Ruang Fisika Kuantum")).toBeTruthy();

    const copyBtns = screen.getAllByTitle("Salin kode");
    expect(copyBtns.length).toBeGreaterThanOrEqual(1);

    await fireEvent.click(copyBtns[0]);
    expect(writeText).toHaveBeenCalledWith("FSK101");
  });

  it("renders room detail page with breadcrumbs, copy actions, and participant list", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, {
      clipboard: { writeText },
    });

    render(RoomDetailPage);

    expect(await screen.findByText("Ruang Sains Komputasi")).toBeTruthy();
    expect(screen.getByText("SNS999")).toBeTruthy();
    expect(screen.getByText("Pak Guru Fisika")).toBeTruthy();
    expect(screen.getAllByText("Andi Siswa").length).toBe(2);
    expect(screen.getByText("Budi Santoso")).toBeTruthy();

    // Copy room link button
    const shareBtn = screen.getByRole("button", { name: /Bagikan Tautan/i });
    await fireEvent.click(shareBtn);
    expect(writeText).toHaveBeenCalled();

    // Copy code button
    const copyCodeBtn = screen.getByTitle("Salin Kode");
    await fireEvent.click(copyCodeBtn);
    expect(writeText).toHaveBeenCalledWith("SNS999");
  });
});
