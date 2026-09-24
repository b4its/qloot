// @vitest-environment jsdom
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, fireEvent, cleanup, waitFor } from "@testing-library/svelte";

const get = vi.fn();
const post = vi.fn();
const put = vi.fn();
vi.mock("../src/lib/api/client", () => ({
  API_BASE: "http://localhost:8000",
  ApiError: class ApiError extends Error {
    status = 0;
  },
  api: {
    get: (...a: unknown[]) => get(...a),
    post: (...a: unknown[]) => post(...a),
    put: (...a: unknown[]) => put(...a),
    patch: vi.fn(),
    delete: vi.fn(),
  },
}));
vi.mock("../src/lib/stores/notifications", () => ({
  notifications: { clear: vi.fn(), refresh: vi.fn() },
}));

import NotificationsPage from "$routes-site/notifications/+page.svelte";

describe("notifications page — preferences (GAME-14)", () => {
  beforeEach(() => {
    cleanup();
    get.mockReset();
    put.mockReset();
    get.mockImplementation((path: string) => {
      if (path.startsWith("/notifications?")) return Promise.resolve([]);
      if (path === "/notifications/preferences") return Promise.resolve({ muted_kinds: [] });
      return Promise.resolve([]);
    });
    put.mockResolvedValue({ muted_kinds: ["reward"] });
  });
  afterEach(() => cleanup());

  it("renders a mute toggle per notification kind and persists the change", async () => {
    render(NotificationsPage);
    await waitFor(() => expect(screen.getByText("Jenis notifikasi")).toBeTruthy());

    const rewardToggle = await screen.findByText("Hadiah");
    await fireEvent.click(rewardToggle);

    await waitFor(() =>
      expect(put).toHaveBeenCalledWith("/notifications/preferences", {
        muted_kinds: ["reward"],
      }),
    );
  });
});
