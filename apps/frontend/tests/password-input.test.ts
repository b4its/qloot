// @vitest-environment jsdom
import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/svelte";

// The component only imports the Icon wrapper (no network), but keep the API
// client mocked defensively in case a consumer is imported in the future.
vi.mock("../src/lib/api/client", () => ({
  API_BASE: "http://localhost:8000",
  ApiError: class ApiError extends Error {
    status = 0;
  },
  api: { get: vi.fn(), post: vi.fn(), put: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}));

import PasswordInput from "$lib/components/PasswordInput.svelte";

describe("PasswordInput", () => {
  beforeEach(() => cleanup());

  it("renders a masked field by default", () => {
    const { container } = render(PasswordInput);
    const input = container.querySelector("input");
    expect(input).toBeTruthy();
    expect(input?.getAttribute("type")).toBe("password");
  });

  it("exposes a toggle button that is pressed=false initially", () => {
    render(PasswordInput);
    const toggle = screen.getByRole("button", { name: /tampilkan kata sandi/i });
    expect(toggle).toHaveAttribute("aria-pressed", "false");
  });

  it("reveals the password when the toggle is clicked", async () => {
    const { container } = render(PasswordInput);
    const input = container.querySelector("input") as HTMLInputElement;
    const toggle = screen.getByRole("button", { name: /tampilkan kata sandi/i });

    await fireEvent.click(toggle);
    expect(input.getAttribute("type")).toBe("text");
    expect(toggle).toHaveAttribute("aria-pressed", "true");
  });

  it("hides the password again on a second click", async () => {
    const { container } = render(PasswordInput);
    const input = container.querySelector("input") as HTMLInputElement;

    await fireEvent.click(screen.getByRole("button", { name: /tampilkan kata sandi/i }));
    await fireEvent.click(screen.getByRole("button", { name: /sembunyikan kata sandi/i }));
    expect(input.getAttribute("type")).toBe("password");
  });

  it("forwards rest props and keeps the design-system input class", () => {
    const { container } = render(PasswordInput, {
      props: { id: "pw", autocomplete: "new-password", required: true, class: "mt-1" },
    });
    const input = container.querySelector("input") as HTMLInputElement;
    expect(input.id).toBe("pw");
    expect(input.getAttribute("autocomplete")).toBe("new-password");
    expect(input.required).toBe(true);
    expect(input.className).toContain("input");
    expect(input.className).toContain("mt-1");
  });

  it("keeps the toggle disabled when the field is disabled", () => {
    render(PasswordInput, { props: { disabled: true } });
    const toggle = screen.getByRole("button", { name: /tampilkan kata sandi/i });
    expect(toggle).toBeDisabled();
  });
});
