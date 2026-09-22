// @vitest-environment jsdom
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, fireEvent, cleanup, waitFor } from "@testing-library/svelte";

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
    patch: vi.fn().mockResolvedValue({}),
    delete: vi.fn(),
  },
}));
vi.mock("$app/stores", () => ({
  page: {
    subscribe: (fn: (v: unknown) => void) => (
      fn({ params: {}, url: new URL("http://x/career/roadmap") }),
      () => {}
    ),
  },
}));
vi.mock("$app/navigation", () => ({ goto: vi.fn() }));

import RoadmapPage from "$routes-site/career/roadmap/+page.svelte";
import { auth } from "../src/lib/stores/auth";

const counselor = {
  id: "t1",
  email: "t@x.com",
  full_name: "Guru BK",
  is_active: true,
  chain_user_ref: "0x0",
  created_at: "2026-01-01T00:00:00Z",
  roles: ["teacher"],
};

describe("career roadmap — counselor review queue", () => {
  beforeEach(() => {
    cleanup();
    get.mockReset();
    post.mockReset();
    auth.setUser(counselor);
    get.mockImplementation((path: string) => {
      if (path === "/career/recommendations") return Promise.resolve([]);
      if (path === "/career/roadmap") return Promise.resolve([]);
      if (path === "/career/recommendations/pending")
        return Promise.resolve([
          { user_id: "s1", display_name: "Siswa Satu", top_major: "Teknik Informatika", count: 3 },
        ]);
      return Promise.resolve([]);
    });
  });
  afterEach(() => auth.setUser(null));

  it("lists students awaiting approval for a counselor", async () => {
    render(RoadmapPage);
    expect(await screen.findByText("Menunggu persetujuan")).toBeTruthy();
    expect(await screen.findByText("Siswa Satu")).toBeTruthy();
  });

  it("approves a student's plan by user id", async () => {
    post.mockResolvedValue({ message: "ok" });
    render(RoadmapPage);
    const btn = await screen.findByRole("button", { name: /^setujui$/i });
    await fireEvent.click(btn);
    await waitFor(() =>
      expect(post).toHaveBeenCalledWith("/career/recommendations/approve?user_id=s1"),
    );
  });
});
