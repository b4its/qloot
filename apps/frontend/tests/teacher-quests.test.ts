// @vitest-environment jsdom
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, fireEvent, cleanup, waitFor } from "@testing-library/svelte";

vi.mock("$app/navigation", () => ({ goto: vi.fn() }));

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

import TeacherQuests from "$routes-panel/teacher/quests/+page.svelte";
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

const quests = [
  {
    id: "q1",
    title: "Kuis Kilat",
    owner_id: "t1",
    status: "open",
    kind: "exam",
    top_n_winners: 3,
    reward_version: 1,
    created_at: "2026-01-01T00:00:00Z",
  },
  {
    id: "q2",
    title: "Tantangan Draf",
    owner_id: "t1",
    status: "draft",
    kind: "exam",
    top_n_winners: 2,
    reward_version: 1,
    created_at: "2026-01-02T00:00:00Z",
  },
  {
    id: "q3",
    title: "Quest Selesai",
    owner_id: "t1",
    status: "finalized",
    kind: "exam",
    top_n_winners: 1,
    reward_version: 1,
    created_at: "2026-01-03T00:00:00Z",
  },
];

describe("teacher quests — overview, filters, and confirmation modal", () => {
  beforeEach(() => {
    cleanup();
    get.mockReset();
    post.mockReset();
    auth.setUser(teacher);
    get.mockImplementation((path: string) => {
      if (path.startsWith("/quests?") || path.startsWith("/quests/limit"))
        return Promise.resolve(quests);
      if (path.startsWith("/quests") && path.endsWith("/winners")) return Promise.resolve([]);
      return Promise.resolve([]);
    });
    post.mockResolvedValue({ allocations_created: 3 });
  });
  afterEach(() => auth.setUser(null));

  it("renders the status metrics", async () => {
    render(TeacherQuests);
    await waitFor(() => expect(screen.getByText("Kuis Kilat")).toBeTruthy());
    // 1 open, 1 finalized.
    expect(document.querySelector('[data-role="open-count"]')?.textContent?.trim()).toBe("1");
    // The "Difinalisasi" metric label + the status chip both render.
    expect(screen.getAllByText("Difinalisasi").length).toBeGreaterThan(0);
  });

  it("opens the confirmation modal before finalizing", async () => {
    render(TeacherQuests);
    await waitFor(() => expect(screen.getByText("Kuis Kilat")).toBeTruthy());

    // Scope to the open quest's card so we hit the right finalize button.
    const card = document.querySelector('[data-quest="q1"]') as HTMLElement;
    const finalizeBtn = card.querySelector("button.btn-primary") as HTMLButtonElement;
    await fireEvent.click(finalizeBtn);
    expect(screen.getByText("Konfirmasi Finalisasi Quest")).toBeTruthy();
    // Not executed until confirmed.
    expect(post).not.toHaveBeenCalled();

    const confirm = document.querySelector('[data-role="confirm-finalize"]') as HTMLButtonElement;
    await fireEvent.click(confirm);
    await waitFor(() => expect(post).toHaveBeenCalledWith("/quests/q1/finalize"));
  });

  it("filters quests by status", async () => {
    render(TeacherQuests);
    await waitFor(() => expect(screen.getByText("Kuis Kilat")).toBeTruthy());

    await fireEvent.click(screen.getByRole("button", { name: "Draf" }));
    await waitFor(() => expect(screen.queryByText("Kuis Kilat")).toBeNull());
    expect(screen.getByText("Tantangan Draf")).toBeTruthy();
  });

  it("searches quests by title", async () => {
    render(TeacherQuests);
    await waitFor(() => expect(screen.getByText("Kuis Kilat")).toBeTruthy());

    const input = screen.getByLabelText("Cari quest") as HTMLInputElement;
    await fireEvent.input(input, { target: { value: "selesai" } });
    await waitFor(() => expect(screen.queryByText("Kuis Kilat")).toBeNull());
    expect(screen.getByText("Quest Selesai")).toBeTruthy();
  });
});
