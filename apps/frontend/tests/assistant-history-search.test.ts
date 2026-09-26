// @vitest-environment jsdom
import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, cleanup, waitFor, fireEvent } from "@testing-library/svelte";

const get = vi.fn();
vi.mock("../src/lib/api/client", () => ({
  API_BASE: "http://localhost:8000",
  API_PREFIX: "/api/v1",
  ApiError: class ApiError extends Error {
    status = 0;
  },
  api: {
    get: (...args: unknown[]) => get(...args),
    post: vi.fn(),
    delete: vi.fn(),
  },
}));

import AssistantPage from "$routes-site/assistant/+page.svelte";

const history = [
  { id: "c-1", title: "Bedanya SNBP dan SNBT?", created_at: "", updated_at: "" },
  { id: "c-2", title: "Kampus untuk teknik", created_at: "", updated_at: "" },
  { id: "c-3", title: "Prospek Ilmu Komputer", created_at: "", updated_at: "" },
  { id: "c-4", title: "Rekomendasi jurusan IPA", created_at: "", updated_at: "" },
];

beforeEach(() => {
  cleanup();
  get.mockReset();
  get.mockImplementation((path: string) => {
    if (path === "/career/assistant/conversations") return Promise.resolve(history);
    return Promise.resolve([]);
  });
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("no stream")));
});

describe("assistant history search + copy + typing affordance", () => {
  it("filters the conversation history by title", async () => {
    render(AssistantPage);
    await waitFor(() => expect(screen.getByText("Kampus untuk teknik")).toBeTruthy());

    const input = (await screen.findByLabelText("Cari percakapan")) as HTMLInputElement;
    await fireEvent.input(input, { target: { value: "kampus" } });
    // "Kampus untuk teknik" stays; the other history title ("Rekomendasi jurusan IPA") is filtered out.
    await waitFor(() => expect(screen.queryByText("Rekomendasi jurusan IPA")).toBeNull());
    expect(screen.getByText("Kampus untuk teknik")).toBeTruthy();
  });

  it("shows the history count", async () => {
    render(AssistantPage);
    await waitFor(() => expect(screen.getByText("Riwayat percakapan · 4")).toBeTruthy());
  });

  it("renders a copy button on a completed bot answer", async () => {
    render(AssistantPage);
    await waitFor(() =>
      expect(screen.getAllByRole("button", { name: "Salin jawaban" }).length).toBeGreaterThan(0),
    );
  });
});
