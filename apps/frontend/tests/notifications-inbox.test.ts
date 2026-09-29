// @vitest-environment jsdom
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, fireEvent, cleanup, waitFor } from "@testing-library/svelte";

const goto = vi.fn();
vi.mock("$app/navigation", () => ({ goto: (...a: unknown[]) => goto(...a) }));

const get = vi.fn();
const post = vi.fn();
const del = vi.fn();
vi.mock("../src/lib/api/client", () => ({
  API_BASE: "http://localhost:8000",
  ApiError: class ApiError extends Error {
    status = 0;
  },
  api: {
    get: (...a: unknown[]) => get(...a),
    post: (...a: unknown[]) => post(...a),
    put: vi.fn(),
    patch: vi.fn(),
    delete: (...a: unknown[]) => del(...a),
  },
}));

const refresh = vi.fn();
const clear = vi.fn();
vi.mock("../src/lib/stores/notifications", () => ({
  notifications: {
    refresh: () => refresh(),
    clear: () => clear(),
  },
}));

import NotificationsPage from "$routes-site/notifications/+page.svelte";

function notif(over: Record<string, unknown> = {}) {
  return {
    id: "n1",
    kind: "reward",
    title: "Kamu dapat 10 OPT!",
    body: "Quest selesai",
    data: { quest_id: "q1" },
    read_at: null,
    created_at: "2026-01-02T00:00:00Z",
    ...over,
  };
}

const seed = {
  items: [
    notif({ id: "n1", kind: "reward", title: "Kamu dapat 10 OPT!", data: { quest_id: "q1" } }),
    notif({
      id: "n2",
      kind: "room",
      title: "Undangan ruang",
      data: { room_id: "r-9" },
      read_at: "2026-01-02T01:00:00Z",
    }),
  ],
  total: 2,
  unread: 1,
  kind_counts: { reward: 1, room: 1 },
};

describe("notifications page — inbox UX (STUDY-09)", () => {
  beforeEach(() => {
    cleanup();
    get.mockReset();
    post.mockReset();
    del.mockReset();
    goto.mockReset();
    refresh.mockReset();
    clear.mockReset();
    get.mockImplementation((path: string) => {
      if (path.startsWith("/notifications/page")) return Promise.resolve(seed);
      if (path === "/notifications/preferences") return Promise.resolve({ muted_kinds: [] });
      return Promise.resolve([]);
    });
    post.mockResolvedValue({});
    del.mockResolvedValue({});
  });
  afterEach(() => cleanup());

  it("renders the metric strip from the bundled page response", async () => {
    render(NotificationsPage);
    await waitFor(() => expect(screen.getByText("Kamu dapat 10 OPT!")).toBeTruthy());
    const unreadCell = document.querySelector('[data-role="unread"]');
    expect(unreadCell?.textContent?.trim()).toBe("1");
  });

  it("deep-links a notification to its context when clicked", async () => {
    render(NotificationsPage);
    await waitFor(() => expect(screen.getByText("Undangan ruang")).toBeTruthy());
    // The read notification (room invite) links to its room.
    await fireEvent.click(screen.getByText("Undangan ruang"));
    await waitFor(() => expect(goto).toHaveBeenCalledWith("/rooms/r-9"));
  });

  it("deep-links a graded exam to the exact attempt result", async () => {
    const examSeed = {
      items: [
        notif({
          id: "n-exam",
          title: "Ujian sudah dinilai",
          data: { exam_id: "e-7", attempt_id: "a-9" },
        }),
      ],
      total: 1,
      unread: 1,
      kind_counts: { reward: 1 },
    };
    get.mockImplementation((path: string) => {
      if (path.startsWith("/notifications/page")) return Promise.resolve(examSeed);
      if (path === "/notifications/preferences") return Promise.resolve({ muted_kinds: [] });
      return Promise.resolve([]);
    });

    render(NotificationsPage);
    await fireEvent.click(await screen.findByText("Ujian sudah dinilai"));
    await waitFor(() => expect(goto).toHaveBeenCalledWith("/exams/e-7/result?attempt=a-9"));
  });

  it("bulk-marks selected notifications read via the batch endpoint", async () => {
    render(NotificationsPage);
    await waitFor(() => expect(screen.getByText("Kamu dapat 10 OPT!")).toBeTruthy());

    const box = screen.getByLabelText("Pilih Kamu dapat 10 OPT!") as HTMLInputElement;
    await fireEvent.click(box);
    await waitFor(() => expect(screen.getByText("1 dipilih")).toBeTruthy());

    await fireEvent.click(screen.getByText("Tandai dibaca"));
    await waitFor(() =>
      expect(post).toHaveBeenCalledWith("/notifications/read-batch", { ids: ["n1"] }),
    );
  });

  it("deletes a single notification through the delete endpoint", async () => {
    render(NotificationsPage);
    await waitFor(() => expect(screen.getByText("Kamu dapat 10 OPT!")).toBeTruthy());

    const delBtn = document.querySelector(
      '[data-notification="n1"] [data-role="delete"]',
    ) as HTMLButtonElement;
    await fireEvent.click(delBtn);
    await waitFor(() => expect(del).toHaveBeenCalledWith("/notifications/n1"));
  });

  it("re-queries the server when a kind chip is selected", async () => {
    render(NotificationsPage);
    await waitFor(() => expect(screen.getByText("Kamu dapat 10 OPT!")).toBeTruthy());
    const callsBefore = get.mock.calls.length;

    await fireEvent.click(screen.getByText(/Ruang \(1\)/));
    await waitFor(() => expect(get.mock.calls.length).toBeGreaterThan(callsBefore));
    expect(get.mock.calls.some((c) => String(c[0]).includes("kind=room"))).toBe(true);
  });

  it("requests read_only when the Dibaca filter is selected", async () => {
    render(NotificationsPage);
    await waitFor(() => expect(screen.getByText("Kamu dapat 10 OPT!")).toBeTruthy());
    const callsBefore = get.mock.calls.length;

    await fireEvent.click(screen.getByText("Dibaca"));
    await waitFor(() => expect(get.mock.calls.length).toBeGreaterThan(callsBefore));
    expect(get.mock.calls.some((c) => String(c[0]).includes("read_only=true"))).toBe(true);
  });

  it("requests oldest_first when the oldest sort is selected", async () => {
    render(NotificationsPage);
    await waitFor(() => expect(screen.getByText("Kamu dapat 10 OPT!")).toBeTruthy());

    await fireEvent.change(screen.getByLabelText("Urutkan"), { target: { value: "oldest" } });
    await waitFor(() =>
      expect(get.mock.calls.some((c) => String(c[0]).includes("oldest_first=true"))).toBe(true),
    );
  });

  it("keeps the read metric consistent with the filtered list", async () => {
    // Filtering returns a filtered `total` but the server's `unread` is always
    // global. Here the filtered page has 1 read + 0 unread rows, yet the global
    // unread count is high — the old `total - unread` would underflow to 0.
    const filteredSeed = {
      items: [
        notif({ id: "r1", kind: "room", title: "Sudah dibaca", read_at: "2026-01-02T01:00:00Z" }),
      ],
      total: 1,
      unread: 9,
      kind_counts: { reward: 1, room: 1 },
    };
    get.mockImplementation((path: string) => {
      if (path.startsWith("/notifications/page")) return Promise.resolve(filteredSeed);
      if (path === "/notifications/preferences") return Promise.resolve({ muted_kinds: [] });
      return Promise.resolve([]);
    });

    render(NotificationsPage);
    await waitFor(() => expect(screen.getByText("Sudah dibaca")).toBeTruthy());
    // Wait for the bundle so the kind chips (from kind_counts) are present.
    await screen.findByText(/Ruang \(1\)/);
    // Apply a kind filter so the metric derives from the visible rows.
    await fireEvent.click(screen.getByText(/Ruang \(1\)/));

    await waitFor(() =>
      expect(document.querySelector('[data-role="read"]')?.textContent?.trim()).toBe("1"),
    );
    expect(document.querySelector('[data-role="unread"]')?.textContent?.trim()).toBe("0");
  });
});
