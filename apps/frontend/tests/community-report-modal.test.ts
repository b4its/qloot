// @vitest-environment jsdom
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, cleanup, fireEvent, waitFor } from "@testing-library/svelte";

vi.mock("$app/stores", () => ({
  page: {
    subscribe: (fn: (v: unknown) => void) => (
      fn({
        params: {},
        url: new URL("http://localhost:3000/community"),
      }),
      () => {}
    ),
  },
}));

vi.mock("../src/lib/stores/auth", () => ({
  auth: {
    subscribe: (fn: (v: unknown) => void) => (
      fn({
        user: { id: "user-current", name: "User Current", handle: "0x123", roles: ["student"] },
      }),
      () => {}
    ),
  },
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

import CommunityPage from "../src/routes/(site)/community/+page.svelte";

const mockPosts = [
  {
    id: "post-1",
    author_id: "user-2",
    author_name: "Budi Santoso",
    handle: "0xabc",
    topic: "Umum",
    body: "Halo semuanya, salam kenal dari Bandung!",
    like_count: 5,
    comment_count: 1,
    liked_by_me: false,
    created_at: "2026-09-26T10:00:00Z",
    comments: [
      {
        id: "comment-1",
        author_id: "user-3",
        author_name: "Siti Rahma",
        body: "Halo Budi, selamat bergabung!",
        created_at: "2026-09-26T10:05:00Z",
      },
    ],
  },
];

describe("community report and interactive moderation modals", () => {
  beforeEach(() => {
    cleanup();
    get.mockReset();
    post.mockReset();
    patch.mockReset();
    del.mockReset();

    get.mockImplementation(async (path: string) => {
      if (path.startsWith("/community/posts/post-1")) return mockPosts[0];
      if (path.startsWith("/community/posts")) return mockPosts;
      if (path === "/community/topics") return [{ name: "Umum", posts: 10 }];
      if (path === "/community/stats") return { members: 100, posts: 25, comments: 40 };
      if (path === "/me/following") return [];
      return [];
    });
    post.mockResolvedValue({ id: "rep-1" });
  });

  afterEach(() => cleanup());

  it("opens report modal on post report click and submits report", async () => {
    render(CommunityPage);
    expect(await screen.findByText("Halo semuanya, salam kenal dari Bandung!")).toBeTruthy();

    const reportBtn = screen.getByRole("button", { name: /Laporkan/i });
    await fireEvent.click(reportBtn);

    // Modal appears
    expect(screen.getByText("Moderasi Komunitas")).toBeTruthy();
    expect(screen.getByText("Laporkan Diskusi")).toBeTruthy();
    expect(screen.getByText("Spam atau promosi tidak relevan")).toBeTruthy();

    // Submit report
    const submitBtn = screen.getByRole("button", { name: "Kirim Laporan" });
    await fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(post).toHaveBeenCalledWith("/community/reports", {
        target_type: "post",
        target_id: "post-1",
        reason: "Spam atau promosi tidak relevan",
      });
    });

    // Success banner
    expect(screen.getByText(/Laporan berhasil dikirim ke tim moderator/)).toBeTruthy();
  });

  it("opens reply modal and submits nested reply", async () => {
    render(CommunityPage);
    expect(await screen.findByText("Halo semuanya, salam kenal dari Bandung!")).toBeTruthy();

    // Toggle open comments
    const commentCountBtn = screen.getByText("1");
    await fireEvent.click(commentCountBtn);

    expect(await screen.findByText("Halo Budi, selamat bergabung!")).toBeTruthy();

    // Click reply button on comment
    const replyBtn = screen.getByRole("button", { name: "Balas komentar" });
    await fireEvent.click(replyBtn);

    // Reply modal
    expect(screen.getByText("Balas Komentar")).toBeTruthy();
    const textarea = screen.getByPlaceholderText("Tulis balasan untuk komentar ini...");
    await fireEvent.input(textarea, { target: { value: "Sama-sama Siti!" } });

    const sendReplyBtn = screen.getByRole("button", { name: "Kirim Balasan" });
    await fireEvent.click(sendReplyBtn);

    await waitFor(() => {
      expect(post).toHaveBeenCalledWith("/community/posts/post-1/comments", {
        body: "Sama-sama Siti!",
        parent_id: "comment-1",
      });
    });
  });
});
