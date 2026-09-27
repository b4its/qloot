// @vitest-environment jsdom
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, fireEvent, cleanup, waitFor } from "@testing-library/svelte";

const goto = vi.fn();
vi.mock("$app/navigation", () => ({ goto: (...a: unknown[]) => goto(...a) }));

const post = vi.fn();
vi.mock("../src/lib/api/client", () => ({
  API_BASE: "http://localhost:8000",
  ApiError: class ApiError extends Error {
    status = 0;
  },
  api: {
    get: vi.fn(),
    post: (...a: unknown[]) => post(...a),
    put: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
}));

import NewExamPage from "$routes-panel/teacher/exams/new/+page.svelte";
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

describe("teacher new-exam form — percent input, presets, preview, and submit", () => {
  beforeEach(() => {
    cleanup();
    post.mockReset();
    goto.mockReset();
    auth.setUser(teacher);
    post.mockResolvedValue({ id: "e1", title: "Ulangan Bab 1" });
  });
  afterEach(() => auth.setUser(null));

  it("keeps submit disabled until the title is valid", async () => {
    render(NewExamPage);
    const submit = screen.getByRole("button", { name: /Buat ujian/i }) as HTMLButtonElement;
    expect(submit.disabled).toBe(true);

    await fireEvent.input(screen.getByPlaceholderText("mis. Ulangan Bab 1"), {
      target: { value: "Ulangan" },
    });
    await waitFor(() => expect(submit.disabled).toBe(false));
  });

  it("shows the percent → basis-points conversion", async () => {
    render(NewExamPage);
    // Default 60% → 6000 bp.
    expect(screen.getByText("60% = 6000 basis points")).toBeTruthy();
  });

  it("applies a duration preset and updates the preview", async () => {
    render(NewExamPage);
    await fireEvent.click(screen.getByRole("button", { name: "30 mnt" }));
    await waitFor(() => expect(screen.getByText("30 menit")).toBeTruthy());
  });

  it("submits passing_score_bp derived from the percent", async () => {
    render(NewExamPage);
    await fireEvent.input(screen.getByPlaceholderText("mis. Ulangan Bab 1"), {
      target: { value: "Ulangan Bab 1" },
    });
    const submit = screen.getByRole("button", { name: /Buat ujian/i }) as HTMLButtonElement;
    await waitFor(() => expect(submit.disabled).toBe(false));
    await fireEvent.click(submit);

    await waitFor(() =>
      expect(post).toHaveBeenCalledWith(
        "/exams",
        expect.objectContaining({ title: "Ulangan Bab 1", passing_score_bp: 6000 }),
      ),
    );
    await waitFor(() => expect(goto).toHaveBeenCalledWith("/teacher/exams/e1"));
  });
});
