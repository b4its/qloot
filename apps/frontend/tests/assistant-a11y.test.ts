// @vitest-environment jsdom
import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, cleanup, waitFor } from "@testing-library/svelte";

vi.mock("../src/lib/api/client", () => ({
  API_BASE: "http://localhost:8000",
  API_PREFIX: "/api/v1",
  ApiError: class ApiError extends Error {
    status = 0;
  },
  api: {
    get: vi.fn().mockResolvedValue([]),
    post: vi.fn(),
    put: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
}));

import AssistantPage from "$routes-site/assistant/+page.svelte";

beforeEach(() => cleanup());

describe("assistant chat accessibility (UIX-02)", () => {
  it("exposes the transcript as a polite live log", () => {
    render(AssistantPage);
    const log = document.querySelector('[role="log"]');
    expect(log).toBeTruthy();
    expect(log?.getAttribute("aria-live")).toBe("polite");
  });

  it("labels the message input", () => {
    render(AssistantPage);
    // The input has an associated <label>.
    expect(screen.getByLabelText(/pertanyaan untuk asisten qlo/i)).toBeTruthy();
  });

  it("uses Indonesian copy and no English UI labels", () => {
    render(AssistantPage);
    expect(screen.getByRole("button", { name: /^kirim$/i })).toBeTruthy();
    expect(document.body.textContent).toContain("Pertanyaan populer");
    expect(document.body.textContent).not.toContain("Send");
    expect(document.body.textContent).not.toContain("Popular questions");
  });

  it("has no fake typing indicator", () => {
    render(AssistantPage);
    expect(document.querySelector(".animate-bounce")).toBeNull();
  });

  it("renders the greeting on mount", async () => {
    render(AssistantPage);
    await waitFor(() =>
      expect(document.body.textContent).toContain("Asisten Qlo"),
    );
  });
});
