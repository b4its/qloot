// @vitest-environment jsdom
import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, cleanup } from "@testing-library/svelte";

vi.mock("../src/lib/api/client", () => ({
  API_BASE: "http://localhost:8000",
  ApiError: class ApiError extends Error {
    status = 0;
  },
  api: { get: vi.fn(), post: vi.fn(), put: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}));

import AssistantPage from "$routes-site/assistant/+page.svelte";

describe("Asisten Qlo page", () => {
  beforeEach(() => cleanup());

  it("names the assistant 'Asisten Qlo' and never the old 'Kulo' alias", () => {
    render(AssistantPage);
    // Heading + intro both use the correct name.
    expect(screen.getByRole("heading", { name: /Asisten Qlo/ })).toBeTruthy();
    expect(document.body.textContent).toContain("Asisten Qlo");
    // The deprecated alias must be gone everywhere on the page.
    expect(document.body.textContent).not.toContain("Kulo");
  });
});
