// @vitest-environment jsdom
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, fireEvent, cleanup, waitFor } from "@testing-library/svelte";

vi.mock("$app/stores", () => ({
  page: {
    subscribe: (fn: (v: unknown) => void) => (
      fn({ params: { id: "q1" }, url: new URL("http://x/teacher/quests/q1") }),
      () => {}
    ),
  },
}));
const goto = vi.fn();
vi.mock("$app/navigation", () => ({ goto: (...a: unknown[]) => goto(...a) }));

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

import QuestDetailPage from "$routes-panel/teacher/quests/[id]/+page.svelte";
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

const quest = {
  id: "q1",
  title: "Sprint Bab 1",
  owner_id: "t1",
  status: "draft",
  kind: "exam",
  top_n_winners: 3,
  reward_version: 1,
  created_at: "2026-01-01T00:00:00Z",
  rules: [
    { rank: 1, reward_amount: 100 },
    { rank: 2, reward_amount: 60 },
    { rank: 3, reward_amount: 40 },
  ],
};

describe("teacher quest detail — rules, metadata, save, and publish confirm", () => {
  beforeEach(() => {
    cleanup();
    get.mockReset();
    post.mockReset();
    patch.mockReset();
    auth.setUser(teacher);
    get.mockImplementation((path: string) => {
      if (path.endsWith("/winners")) return Promise.resolve([]);
      if (path.startsWith("/quests/")) return Promise.resolve(quest);
      return Promise.resolve([]);
    });
    post.mockResolvedValue({});
    patch.mockResolvedValue({ ...quest, title: "Sprint Bab 2" });
  });
  afterEach(() => auth.setUser(null));

  it("shows the reward rules and total pool", async () => {
    render(QuestDetailPage);
    await waitFor(() => expect(screen.getByText("Hadiah per peringkat")).toBeTruthy());
    // 100 + 60 + 40 = 200 OPT.
    expect(screen.getByText("200 OPT")).toBeTruthy();
  });

  it("disables save until a change is made", async () => {
    render(QuestDetailPage);
    await waitFor(() => expect(screen.getByRole("button", { name: /Tersimpan/i })).toBeTruthy());
    const save = screen.getByRole("button", { name: /Tersimpan/i }) as HTMLButtonElement;
    expect(save.disabled).toBe(true);

    const titleInput = document.querySelector("input.input") as HTMLInputElement;
    await fireEvent.input(titleInput, { target: { value: "Sprint Bab 2" } });
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /Simpan perubahan/i })).toBeTruthy(),
    );
  });

  it("patches the quest on save", async () => {
    render(QuestDetailPage);
    await waitFor(() => expect(screen.getByText("Hadiah per peringkat")).toBeTruthy());
    const titleInput = document.querySelector("input.input") as HTMLInputElement;
    await fireEvent.input(titleInput, { target: { value: "Sprint Bab 2" } });
    await fireEvent.click(screen.getByRole("button", { name: /Simpan perubahan/i }));
    await waitFor(() =>
      expect(patch).toHaveBeenCalledWith(
        "/quests/q1",
        expect.objectContaining({ title: "Sprint Bab 2" }),
      ),
    );
  });

  it("edits description and the open/close window", async () => {
    patch.mockResolvedValue({ ...quest, title: "Sprint Bab 1" });
    render(QuestDetailPage);
    await waitFor(() => expect(screen.getByText("Hadiah per peringkat")).toBeTruthy());

    const desc = screen.getByPlaceholderText(/Ringkasan aturan/) as HTMLTextAreaElement;
    await fireEvent.input(desc, { target: { value: "Aturan baru" } });
    const opens = document.querySelector('input[type="datetime-local"]') as HTMLInputElement;
    await fireEvent.input(opens, { target: { value: "2026-03-01T08:00" } });

    await fireEvent.click(screen.getByRole("button", { name: /Simpan perubahan/i }));
    await waitFor(() =>
      expect(patch).toHaveBeenCalledWith(
        "/quests/q1",
        expect.objectContaining({
          description: "Aturan baru",
          opens_at: expect.stringContaining("2026-03-01"),
        }),
      ),
    );
  });

  it("confirms before publishing", async () => {
    render(QuestDetailPage);
    await waitFor(() => expect(screen.getByRole("button", { name: /Terbitkan/i })).toBeTruthy());

    await fireEvent.click(screen.getByRole("button", { name: /Terbitkan/i }));
    expect(screen.getByText("Terbitkan Quest")).toBeTruthy();
    expect(post).not.toHaveBeenCalled();

    const confirm = document.querySelector('[data-role="confirm-publish"]') as HTMLButtonElement;
    await fireEvent.click(confirm);
    await waitFor(() => expect(post).toHaveBeenCalledWith("/quests/q1/publish"));
  });
});
