// @vitest-environment jsdom
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, fireEvent, cleanup, waitFor } from "@testing-library/svelte";

vi.mock("$app/navigation", () => ({ goto: vi.fn() }));
vi.mock("$app/stores", () => ({
  page: {
    subscribe: (fn: (v: unknown) => void) => (
      fn({ url: new URL("http://x/community"), params: {} }),
      () => {}
    ),
  },
}));

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
    put: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
}));

import { auth } from "$lib/stores/auth";
import CommunityPage from "$routes-site/community/+page.svelte";

const student = {
  id: "u1",
  email: "s@x.com",
  full_name: "Student",
  is_active: true,
  chain_user_ref: "0x0",
  created_at: "2026-01-01T00:00:00Z",
  roles: ["student"],
};

const basePost = {
  id: "p1",
  author_id: "u2",
  author_name: "Andi",
  body: "Halo semua",
  topic: "Umum",
  like_count: 0,
  comment_count: 1,
  liked_by_me: false,
  created_at: "2026-01-01T00:00:00Z",
  hidden: false,
  comments: [],
};

const existingComment = {
  id: "c1",
  author_id: "u2",
  author_name: "Andi",
  body: "Komentar pertama",
  parent_id: null,
  edited_at: null,
  created_at: "2026-01-01T00:00:00Z",
};

describe("community — replying to a comment", () => {
  beforeEach(() => {
    cleanup();
    get.mockReset();
    post.mockReset();
    auth.setUser(student);
  });
  afterEach(() => auth.setUser(null));

  it("shows the new reply in the thread right after submitting it", async () => {
    let replied = false;
    get.mockImplementation((path: string) => {
      if (path === "/community/posts/p1") {
        const comments = replied
          ? [
              existingComment,
              {
                id: "c2",
                author_id: "u1",
                author_name: "Student",
                body: "Balasanku",
                parent_id: "c1",
                edited_at: null,
                created_at: "2026-01-01T00:01:00Z",
              },
            ]
          : [existingComment];
        return Promise.resolve({ ...basePost, comment_count: comments.length, comments });
      }
      if (path.startsWith("/community/posts")) return Promise.resolve([basePost]);
      if (path === "/community/topics") return Promise.resolve([]);
      if (path.startsWith("/community/stats"))
        return Promise.resolve({ members: 1, posts: 1, comments: 1 });
      if (path === "/me/following") return Promise.resolve([]);
      return Promise.resolve([]);
    });
    post.mockImplementation((path: string) => {
      if (path === "/community/posts/p1/comments") replied = true;
      return Promise.resolve({});
    });

    render(CommunityPage);
    await waitFor(() => expect(screen.getByText("Halo semua")).toBeTruthy());

    // Open the thread by clicking the comment-count button (labelled "1").
    const counts = screen.getAllByRole("button", { name: "1" });
    await fireEvent.click(counts[counts.length - 1]);
    await waitFor(() => expect(screen.getByText("Komentar pertama")).toBeTruthy());

    // Reply.
    await fireEvent.click(screen.getByRole("button", { name: "Balas komentar" }));
    const box = await screen.findByLabelText("Isi balasan");
    await fireEvent.input(box, { target: { value: "Balasanku" } });
    await fireEvent.click(screen.getByRole("button", { name: /Kirim Balasan/ }));

    // The freshly loaded reply must render inside the comment thread (it
    // previously did not, because the stale post object replaced the reloaded
    // one).
    const reply = await screen.findByText("Balasanku");
    expect(reply.closest('[data-thread="p1"]')).not.toBeNull();
  });
});
