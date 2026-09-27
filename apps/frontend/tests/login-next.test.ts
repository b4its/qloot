// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/svelte";

const { goto, login, page } = vi.hoisted(() => {
  let value = { url: new URL("http://localhost:3000/login") };
  const subscribers = new Set<(next: typeof value) => void>();
  return {
    goto: vi.fn(),
    login: vi.fn(),
    page: {
      subscribe(run: (next: typeof value) => void) {
        subscribers.add(run);
        run(value);
        return () => subscribers.delete(run);
      },
      set(next: typeof value) {
        value = next;
        subscribers.forEach((run) => run(value));
      },
    },
  };
});

vi.mock("$app/navigation", () => ({ goto: (...args: unknown[]) => goto(...args) }));
vi.mock("$app/stores", () => ({ page }));
vi.mock("../src/lib/stores/auth", () => ({ auth: { login } }));
vi.mock("../src/lib/api/client", () => ({
  ApiError: class ApiError extends Error {},
}));

import LoginPage from "$routes-site/login/+page.svelte";

async function submitWithNext(next?: string) {
  const url = new URL("http://localhost:3000/login");
  if (next !== undefined) url.searchParams.set("next", next);
  page.set({ url });
  render(LoginPage);
  await fireEvent.input(screen.getByLabelText("Email"), { target: { value: "user@example.com" } });
  await fireEvent.input(screen.getByLabelText("Kata sandi"), { target: { value: "password" } });
  await fireEvent.click(screen.getByRole("button", { name: "Masuk" }));
  await waitFor(() => expect(login).toHaveBeenCalled());
}

describe("login next destination", () => {
  beforeEach(() => {
    cleanup();
    goto.mockReset();
    login.mockReset().mockResolvedValue({});
  });

  it("honors a same-origin root-relative destination", async () => {
    await submitWithNext("/courses/one?tab=lessons#current");

    expect(goto).toHaveBeenCalledWith("/courses/one?tab=lessons#current");
  });

  it.each(["https://evil.example/phish", "//evil.example/phish", "/\\evil.example/phish"])(
    "rejects unsafe destination %s",
    async (next) => {
      await submitWithNext(next);

      expect(goto).toHaveBeenCalledWith("/dashboard");
    },
  );
});
