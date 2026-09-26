// @vitest-environment jsdom
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, cleanup, fireEvent, waitFor } from "@testing-library/svelte";

vi.mock("$app/stores", () => ({
  page: {
    subscribe: (fn: (v: unknown) => void) => (
      fn({ params: {}, url: new URL("http://localhost:3000/community") }),
      () => {}
    ),
  },
}));

const get = vi.fn();
vi.mock("../src/lib/api/client", () => ({
  API_BASE: "http://localhost:8000",
  ApiError: class ApiError extends Error {
    status = 0;
  },
  api: {
    get: (...a: unknown[]) => get(...a),
    post: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
}));

import CommunityPage from "$routes-site/community/+page.svelte";
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

const posts = [
  {
    id: "p1",
    author_id: "a1",
    author_name: "Andi",
    handle: "0xaaa",
    topic: "Umum",
    body: "Tips belajar matematika",
    like_count: 1,
    comment_count: 0,
    liked_by_me: false,
    created_at: "2026-01-01T00:00:00Z",
    comments: [],
  },
];

describe("community feed — free-text search", () => {
  beforeEach(() => {
    cleanup();
    get.mockReset();
    auth.setUser(student);
    get.mockImplementation((path: string) => {
      if (path.startsWith("/community/posts")) return Promise.resolve(posts);
      if (path.startsWith("/community/topics")) return Promise.resolve([]);
      if (path.startsWith("/community/stats"))
        return Promise.resolve({ members: 1, posts: 1, comments: 0 });
      if (path.startsWith("/me/following")) return Promise.resolve([]);
      return Promise.resolve([]);
    });
  });
  afterEach(() => auth.setUser(null));

  it("sends the search term to the server after debounce", async () => {
    render(CommunityPage);
    await waitFor(() => expect(screen.getByText("Tips belajar matematika")).toBeTruthy());

    const input = screen.getByLabelText("Cari diskusi") as HTMLInputElement;
    await fireEvent.input(input, { target: { value: "matematika" } });
    await waitFor(
      () => expect(get.mock.calls.some((c) => String(c[0]).includes("q=matematika"))).toBe(true),
      { timeout: 1500 },
    );
  });

  it("shows a result count once a search is active", async () => {
    render(CommunityPage);
    await waitFor(() => expect(screen.getByText("Tips belajar matematika")).toBeTruthy());

    const input = screen.getByLabelText("Cari diskusi") as HTMLInputElement;
    await fireEvent.input(input, { target: { value: "matematika" } });
    await waitFor(() =>
      expect(document.querySelector('[data-role="search-count"]')?.textContent).toContain(
        '1 hasil untuk "matematika"',
      ),
    );
  });
});
