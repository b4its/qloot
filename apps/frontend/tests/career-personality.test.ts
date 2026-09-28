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
    patch: vi.fn(),
    delete: vi.fn(),
  },
}));

import PersonalityPage from "$routes-site/career/personality/+page.svelte";

const result = {
  openness: 90,
  conscientiousness: 70,
  extraversion: 60,
  agreeableness: 80,
  neuroticism: 30,
  summary: "Kamu analitis dan terbuka.",
  created_at: "2026-01-01T00:00:00Z",
};

describe("career personality — progress gate and results", () => {
  beforeEach(() => {
    cleanup();
    get.mockReset();
    post.mockReset();
    get.mockResolvedValue(null);
    post.mockResolvedValue(result);
  });
  afterEach(() => cleanup());

  it("disables submit until every question is answered", async () => {
    render(PersonalityPage);
    await waitFor(() => expect(screen.getByRole("button", { name: /Jawab semua/i })).toBeTruthy());
    const submit = document.querySelector('[data-role="submit"]') as HTMLButtonElement;
    expect(submit.disabled).toBe(true);
  });

  it("enables submit once all statements are answered and posts the answers", async () => {
    render(PersonalityPage);
    await waitFor(() => expect(screen.getByRole("progressbar")).toBeTruthy());

    // Answer every question by picking the "Sangat setuju" (5) button.
    const agreeButtons = screen.getAllByRole("button", { name: /Sangat setuju/i });
    for (const b of agreeButtons) await fireEvent.click(b);

    await waitFor(() => {
      const submit = document.querySelector('[data-role="submit"]') as HTMLButtonElement;
      expect(submit.disabled).toBe(false);
    });
    const submit = document.querySelector('[data-role="submit"]') as HTMLButtonElement;
    await fireEvent.click(submit);
    await waitFor(() =>
      expect(post).toHaveBeenCalledWith("/career/personality", { answers: expect.any(Array) }),
    );
  });

  it("shows the dominant trait when a previous result exists", async () => {
    get.mockResolvedValue(result);
    render(PersonalityPage);
    await waitFor(() => expect(screen.getByText("Ciri dominan")).toBeTruthy());
    // Keterbukaan (90) is the highest trait; it appears in the dominant card.
    expect(screen.getAllByText("Keterbukaan").length).toBeGreaterThan(0);
    expect(screen.getByText("Terendah: Neurotisisme (30)")).toBeTruthy();
  });

  it("offers retake while keeping the saved result until a new test is sent", async () => {
    get.mockResolvedValue(result);
    render(PersonalityPage);
    await waitFor(() => expect(screen.getByRole("button", { name: /Ulangi/ })).toBeTruthy());

    // Entering retake resets the questionnaire but keeps the stored profile on
    // screen, so navigating away never loses a saved result.
    await fireEvent.click(screen.getByRole("button", { name: /Ulangi/ }));
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /Batal ulangi/ })).toBeTruthy(),
    );
    expect(screen.getByText("Ciri dominan")).toBeTruthy();
    const submit = document.querySelector('[data-role="submit"]') as HTMLButtonElement;
    expect(submit.disabled).toBe(true);

    // Cancelling returns to the read-only result view.
    await fireEvent.click(screen.getByRole("button", { name: /Batal ulangi/ }));
    await waitFor(() => expect(screen.getByRole("button", { name: /Ulangi/ })).toBeTruthy());
    expect(screen.getByText("Ciri dominan")).toBeTruthy();
  });
});
