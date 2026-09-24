// @vitest-environment jsdom
import { describe, it, expect, beforeEach, vi } from "vitest";

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

import { auth } from "../src/lib/stores/auth";

function user(expiresInMs: number) {
  return {
    id: "u-1",
    email: "a@b.com",
    full_name: "Test User",
    is_active: true,
    chain_user_ref: "0x1",
    created_at: "2026-01-01T00:00:00Z",
    roles: ["student"],
    session_expires_at: new Date(Date.now() + expiresInMs).toISOString(),
  };
}

beforeEach(() => {
  get.mockReset();
  post.mockReset();
  auth.setUser(null);
});

describe("session refresh wiring (AUTH-10)", () => {
  it("rotates the token when the session is near expiry", async () => {
    get.mockResolvedValue(user(60 * 60 * 1000)); // 1 hour left
    post.mockResolvedValue(user(14 * 24 * 60 * 60 * 1000)); // fresh 14 days

    await auth.load();

    expect(post).toHaveBeenCalledWith("/auth/refresh");
  });

  it("does not refresh while the session is far from expiry", async () => {
    get.mockResolvedValue(user(10 * 24 * 60 * 60 * 1000)); // 10 days left

    await auth.load();

    expect(post).not.toHaveBeenCalled();
  });

  it("keeps the user when an optional refresh fails", async () => {
    get.mockResolvedValue(user(60 * 1000));
    post.mockRejectedValue(new Error("boom"));

    await auth.load();

    expect(post).toHaveBeenCalledWith("/auth/refresh");
    let current: unknown;
    const unsub = auth.subscribe((s) => (current = s.user));
    unsub();
    expect((current as { email: string }).email).toBe("a@b.com");
  });
});
