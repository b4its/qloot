// @vitest-environment jsdom
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, fireEvent, cleanup, waitFor } from "@testing-library/svelte";

const get = vi.fn();
const post = vi.fn();
vi.mock("../src/lib/api/client", () => ({
  API_BASE: "http://localhost:8000",
  wsUrl: (p: string) => `ws://localhost:8000${p}`,
  ApiError: class ApiError extends Error {
    status = 0;
  },
  api: {
    get: (...a: unknown[]) => get(...a),
    post: (...a: unknown[]) => post(...a),
    put: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
}));

// The room page reads $page.params.roomId and opens a WebSocket.
vi.mock("$app/stores", () => ({
  page: {
    subscribe: (fn: (v: unknown) => void) => (
      fn({ params: { roomId: "r1" }, url: new URL("http://x/rooms/r1") }),
      () => {}
    ),
  },
}));
vi.mock("$app/navigation", () => ({ goto: vi.fn() }));

class FakeWS {
  onopen: (() => void) | null = null;
  onmessage: ((e: unknown) => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;
  close() {}
  send() {}
}
// @ts-expect-error jsdom has no WebSocket by default
globalThis.WebSocket = FakeWS;

import RoomPage from "$routes-site/rooms/[roomId]/+page.svelte";
import CommunityPage from "$routes-site/community/+page.svelte";
import CertificatesPage from "$routes-site/certificates/+page.svelte";
import ProfilePage from "$routes-site/profile/+page.svelte";
import { auth } from "../src/lib/stores/auth";

const student = {
  id: "u-1",
  email: "a@b.com",
  full_name: "Test User",
  is_active: true,
  chain_user_ref: "0x1",
  created_at: "2026-01-01T00:00:00Z",
  roles: ["student"],
};

describe("room page shows participant display names", () => {
  beforeEach(() => {
    cleanup();
    get.mockReset();
    auth.setUser(student);
    get.mockImplementation((path: string) => {
      if (path === "/rooms/r1")
        return Promise.resolve({ id: "r1", name: "Room", code: "ABC123", status: "open" });
      if (path === "/rooms/r1/participants")
        return Promise.resolve([
          {
            id: "m1",
            room_id: "r1",
            user_id: "u-2",
            role: "student",
            is_present: true,
            joined_at: "2026-01-01T00:00:00Z",
            display_name: "Budi Santoso",
          },
        ]);
      if (path === "/rankings/rooms/r1")
        return Promise.resolve({
          scope: "room",
          entries: [{ rank: 1, user_id: "u-2", display_name: "Budi Santoso", score_bp: 9000 }],
        });
      return Promise.resolve([]);
    });
  });
  afterEach(() => auth.setUser(null));

  it("renders the participant's name instead of a raw id", async () => {
    render(RoomPage);
    expect((await screen.findAllByText("Budi Santoso")).length).toBeGreaterThan(0);
    // The raw uuid is not shown anywhere in the roster.
    expect(screen.queryByText(/u-2/)).toBeNull();
  });

  it("shows the leaderboard name", async () => {
    render(RoomPage);
    await waitFor(() => expect(screen.getByText("90.0%")).toBeTruthy());
    expect(screen.getAllByText("Budi Santoso").length).toBeGreaterThan(0);
  });
});

describe("community post interactions", () => {
  const samplePost = {
    id: "p1",
    author_name: "Andi",
    handle: "0xabc",
    body: "Halo dunia",
    topic: "Umum",
    like_count: 3,
    comment_count: 0,
    liked_by_me: false,
    created_at: "2026-01-01T00:00:00Z",
    comments: [],
  };
  beforeEach(() => {
    cleanup();
    get.mockReset();
    post.mockReset();
    auth.setUser(student);
    get.mockImplementation((path: string) => {
      if (path.startsWith("/community/posts?")) return Promise.resolve([samplePost]);
      if (path === "/community/topics") return Promise.resolve([{ topic: "Umum", count: 1 }]);
      if (path === "/community/stats")
        return Promise.resolve({ members: 1, posts: 1, comments: 0 });
      return Promise.resolve([]);
    });
  });
  afterEach(() => auth.setUser(null));

  it("renders the post with an anchor id for deep-linking", async () => {
    const { container } = render(CommunityPage);
    await waitFor(() => expect(screen.getByText("Halo dunia")).toBeTruthy());
    expect(container.querySelector("#post-p1")).toBeTruthy();
  });

  it("copies a deep-linked share URL that matches the anchor", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, { clipboard: { writeText } });
    render(CommunityPage);
    await waitFor(() => expect(screen.getByText("Bagikan")).toBeTruthy());
    await fireEvent.click(screen.getByText("Bagikan"));
    await waitFor(() => expect(writeText).toHaveBeenCalled());
    expect(writeText.mock.calls[0][0]).toContain("/community#post-p1");
    // Transient confirmation appears.
    expect(await screen.findByText("Tersalin!")).toBeTruthy();
  });
});

describe("certificates download produces a real document", () => {
  const cert = {
    id: "c1",
    credential_id: "cred-1",
    course_title: "Fisika Dasar",
    recipient_name: "Test User",
    issued_by: "Guru A",
    issued_at: "2026-01-01T00:00:00Z",
    edition_number: 1,
    edition_total: 10,
  };
  beforeEach(() => {
    cleanup();
    get.mockReset();
    auth.setUser(student);
    get.mockImplementation((path: string) =>
      path.startsWith("/certificates") ? Promise.resolve([cert]) : Promise.resolve([]),
    );
  });
  afterEach(() => auth.setUser(null));

  it("downloads an HTML certificate (not a .txt)", async () => {
    const createObjectURL = vi.fn(() => "blob:x");
    const revokeObjectURL = vi.fn();
    Object.assign(URL, { createObjectURL, revokeObjectURL });
    const click = vi.fn();
    const origCreate = document.createElement.bind(document);
    vi.spyOn(document, "createElement").mockImplementation((tag: string) => {
      const el = origCreate(tag);
      if (tag === "a") el.click = click as unknown as () => void;
      return el;
    });
    render(CertificatesPage);
    await waitFor(() => expect(screen.getByText("Unduh")).toBeTruthy());
    await fireEvent.click(screen.getByText("Unduh"));
    expect(createObjectURL).toHaveBeenCalled();
    expect(click).toHaveBeenCalled();
    vi.restoreAllMocks();
  });

  it("pre-fills the LinkedIn add-certification link", async () => {
    render(CertificatesPage);
    const link = (await screen.findByRole("link", { name: /linkedin/i })) as HTMLAnchorElement;
    expect(link.getAttribute("href")).toContain("certId=cred-1");
    expect(link.getAttribute("href")).toContain("name=Fisika");
  });
});

describe("profile shows real account status", () => {
  beforeEach(() => {
    cleanup();
    get.mockReset();
    get.mockImplementation((path: string) => {
      if (path === "/auth/sessions") return Promise.resolve([]);
      if (path === "/gamification/me") return Promise.resolve(null);
      return Promise.resolve([]);
    });
  });
  afterEach(() => auth.setUser(null));

  it("shows 'Nonaktif' when the user is inactive", async () => {
    auth.setUser({ ...student, is_active: false });
    render(ProfilePage);
    expect(await screen.findByText("Nonaktif")).toBeTruthy();
  });

  it("shows 'Aktif' when the user is active", async () => {
    auth.setUser({ ...student, is_active: true });
    render(ProfilePage);
    expect(await screen.findByText("Aktif")).toBeTruthy();
  });
});
