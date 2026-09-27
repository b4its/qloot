// @vitest-environment jsdom
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, fireEvent, cleanup, waitFor } from "@testing-library/svelte";

const goto = vi.fn();
vi.mock("$app/navigation", () => ({ goto: (...a: unknown[]) => goto(...a) }));

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

import NewQuestPage from "$routes-panel/teacher/quests/new/+page.svelte";
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

describe("teacher new-quest form — rank sync, preview, and submit", () => {
  beforeEach(() => {
    cleanup();
    get.mockReset();
    post.mockReset();
    goto.mockReset();
    auth.setUser(teacher);
    get.mockResolvedValue([]);
    post.mockResolvedValue({ id: "q1", title: "Sprint Bab 1" });
  });
  afterEach(() => auth.setUser(null));

  it("keeps the reward columns in sync with the winner count", async () => {
    render(NewQuestPage);
    // Default 3 winners → 3 reward inputs (#1..#3).
    expect(screen.getByLabelText("Hadiah peringkat 1")).toBeTruthy();
    expect(screen.queryByLabelText("Hadiah peringkat 4")).toBeNull();

    // The winner-count input is the number input capped at 50.
    const winnersInput = document.querySelector(
      'input[type="number"][max="50"]',
    ) as HTMLInputElement;
    await fireEvent.input(winnersInput, { target: { value: "5" } });

    await waitFor(() => expect(screen.getByLabelText("Hadiah peringkat 5")).toBeTruthy());
    // Total pool reflects 5 ranks.
    expect(screen.getByText(/Total pool/)).toBeTruthy();
  });

  it("updates the live preview with the title and pool", async () => {
    render(NewQuestPage);
    await fireEvent.input(screen.getByPlaceholderText("mis. Sprint Bab 1"), {
      target: { value: "Sprint Bab 1" },
    });
    await waitFor(() => expect(screen.getByText("Sprint Bab 1")).toBeTruthy());
    expect(screen.getByText(/Peringkat #1/)).toBeTruthy();
  });

  it("posts rules for every winner and redirects", async () => {
    render(NewQuestPage);
    await fireEvent.input(screen.getByPlaceholderText("mis. Sprint Bab 1"), {
      target: { value: "Sprint Bab 1" },
    });
    const submit = screen.getByRole("button", { name: /Buat quest/i }) as HTMLButtonElement;
    await waitFor(() => expect(submit.disabled).toBe(false));
    await fireEvent.click(submit);

    await waitFor(() => expect(post).toHaveBeenCalled());
    const [path, payload] = post.mock.calls[0];
    expect(path).toBe("/quests");
    expect(payload.top_n_winners).toBe(3);
    expect(payload.rules).toHaveLength(3);
    expect(payload.rules[0]).toEqual({ rank: 1, reward_amount: 100 });
    await waitFor(() => expect(goto).toHaveBeenCalledWith("/teacher/quests/q1"));
  });
});
