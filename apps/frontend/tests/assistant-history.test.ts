// @vitest-environment jsdom
import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, cleanup, waitFor, fireEvent } from "@testing-library/svelte";

const get = vi.fn();
const post = vi.fn();
vi.mock("../src/lib/api/client", () => ({
  API_BASE: "http://localhost:8000",
  ApiError: class ApiError extends Error {
    status = 0;
  },
  api: {
    get: (...args: unknown[]) => get(...args),
    post: (...args: unknown[]) => post(...args),
  },
}));

import AssistantPage from "$routes-site/assistant/+page.svelte";

beforeEach(() => {
  cleanup();
  get.mockReset();
  post.mockReset();
  get.mockResolvedValue([]);
});

describe("assistant conversation history (CARE-01)", () => {
  it("loads the conversation list on mount", async () => {
    render(AssistantPage);
    await waitFor(() =>
      expect(get).toHaveBeenCalledWith("/career/assistant/conversations"),
    );
  });

  it("sends the active conversation_id on follow-up turns", async () => {
    get.mockImplementation((path: string) => {
      if (path === "/career/assistant/conversations") {
        return Promise.resolve([{ id: "c-1", title: "SNBP?", created_at: "", updated_at: "" }]);
      }
      if (path === "/career/assistant/conversations/c-1") {
        return Promise.resolve({
          id: "c-1",
          title: "SNBP?",
          created_at: "",
          updated_at: "",
          messages: [
            { id: "m1", role: "user", content: "Apa itu SNBP?", created_at: "" },
            { id: "m2", role: "assistant", content: "SNBP tanpa tes.", created_at: "" },
          ],
        });
      }
      return Promise.resolve({});
    });
    post.mockResolvedValue({ answer: "ok", confidence_bp: 8000, conversation_id: "c-1" });
    render(AssistantPage);

    // Open the existing conversation so follow-ups carry its id.
    await waitFor(() => expect(screen.getByText("SNBP?")).toBeTruthy());
    await fireEvent.click(screen.getByText("SNBP?"));
    await waitFor(() => expect(document.body.textContent).toContain("SNBP tanpa tes."));

    const input = screen.getByPlaceholderText(/Tanyakan jurusan/i);
    await fireEvent.input(input, { target: { value: "dan biayanya?" } });
    await fireEvent.keyDown(input, { key: "Enter" });

    await waitFor(() =>
      expect(post).toHaveBeenCalledWith("/career/assistant", {
        message: "dan biayanya?",
        conversation_id: "c-1",
      }),
    );
  });

  it("offers a new-conversation control", async () => {
    render(AssistantPage);
    expect(screen.getByRole("button", { name: /percakapan baru/i })).toBeTruthy();
  });
});
