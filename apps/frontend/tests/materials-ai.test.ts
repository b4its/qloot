// @vitest-environment jsdom
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, fireEvent, cleanup, waitFor } from "@testing-library/svelte";

const get = vi.fn();
const post = vi.fn();
const patch = vi.fn();
vi.mock("../src/lib/api/client", () => ({
  API_BASE: "http://localhost:8000",
  ApiError: class ApiError extends Error {
    status = 0;
  },
  api: {
    get: (...a: unknown[]) => get(...a),
    post: (...a: unknown[]) => post(...a),
    put: vi.fn(),
    patch: (...a: unknown[]) => patch(...a),
    delete: vi.fn(),
  },
}));

// The materials page reads $page.params.id.
vi.mock("$app/stores", () => ({
  page: {
    subscribe: (fn: (v: unknown) => void) => (
      fn({ params: { id: "m1" }, url: new URL("http://x/teacher/materials/m1") }),
      () => {}
    ),
  },
}));
vi.mock("$app/navigation", () => ({ goto: vi.fn() }));

import MaterialsPage from "$routes-panel/teacher/materials/[id]/+page.svelte";
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

const material = {
  id: "m1",
  owner_id: "t1",
  filename: "Fisika.pdf",
  content_type: "application/pdf",
  size_bytes: 100,
  checksum_sha256: "abc",
  status: "ready",
  created_at: "2026-01-01T00:00:00Z",
};

describe("teacher materials — AI question generation", () => {
  beforeEach(() => {
    cleanup();
    get.mockReset();
    post.mockReset();
    patch.mockReset();
    patch.mockResolvedValue({});
    auth.setUser(teacher);
    get.mockImplementation((path: string) => {
      if (path === "/materials/m1") return Promise.resolve(material);
      if (path === "/materials/m1/questions") return Promise.resolve([]);
      return Promise.resolve([]);
    });
  });
  afterEach(() => auth.setUser(null));

  it("renders the generate card with an async toggle", async () => {
    render(MaterialsPage);
    expect(await screen.findByText("Buat soal dengan AI")).toBeTruthy();
    expect(screen.getByText(/Antrean \(async\)/)).toBeTruthy();
  });

  it("uses the synchronous endpoint by default", async () => {
    post.mockResolvedValue([
      { id: "q1", prompt: "Apa itu gaya?", correct_answer: "F = ma", review_status: "pending" },
    ]);
    render(MaterialsPage);
    await screen.findByText("Buat soal dengan AI");
    await fireEvent.click(screen.getByRole("button", { name: /buat soal/i }));
    await waitFor(() => expect(screen.getByText(/Apa itu gaya\?/)).toBeTruthy());
    expect(post.mock.calls[0][0]).toContain("generate-questions-sync");
  });

  it("enqueues an async job when the toggle is on", async () => {
    post.mockResolvedValue({ job_id: "job-1", status: "queued" });
    get.mockImplementation((path: string) => {
      if (path === "/materials/m1") return Promise.resolve(material);
      if (path === "/ai/jobs/job-1")
        return Promise.resolve({
          id: "job-1",
          kind: "generation",
          status: "done",
          attempts: 1,
          created_at: "2026-01-01T00:00:00Z",
        });
      return Promise.resolve([]);
    });
    render(MaterialsPage);
    await screen.findByText("Buat soal dengan AI");
    await fireEvent.click(screen.getByRole("checkbox"));
    await fireEvent.click(screen.getByRole("button", { name: /buat soal/i }));
    await waitFor(() => expect(post).toHaveBeenCalled());
    // The enqueue goes to the async endpoint (no -sync suffix).
    const enqueued = post.mock.calls[0][0] as string;
    expect(enqueued).toBe("/materials/m1/generate-questions");
  });

  it("offers bulk approve for pending drafts", async () => {
    post.mockResolvedValue([
      { id: "q1", prompt: "Soal satu?", correct_answer: "A", review_status: "pending" },
      { id: "q2", prompt: "Soal dua?", correct_answer: "B", review_status: "pending" },
    ]);
    render(MaterialsPage);
    await screen.findByText("Buat soal dengan AI");
    await fireEvent.click(screen.getByRole("button", { name: /buat soal/i }));
    await screen.findByText(/Soal satu\?/);
    const bulk = await screen.findByRole("button", { name: /setujui semua draf/i });
    await fireEvent.click(bulk);
    await waitFor(() => expect(patch).toHaveBeenCalled());
    // Each pending draft was approved.
    expect(patch.mock.calls.length).toBeGreaterThanOrEqual(2);
    expect(
      patch.mock.calls.every(
        (c) => (c[1] as { review_status: string }).review_status === "approved",
      ),
    ).toBe(true);
  });
});
