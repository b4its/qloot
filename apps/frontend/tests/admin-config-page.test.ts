// @vitest-environment jsdom
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, cleanup, waitFor } from "@testing-library/svelte";

vi.mock("$app/navigation", () => ({ goto: vi.fn() }));

const get = vi.fn();
vi.mock("../src/lib/api/client", () => ({
  API_BASE: "http://localhost:8000",
  ApiError: class ApiError extends Error {
    status = 0;
  },
  api: {
    get: (...a: unknown[]) => get(...a),
    post: vi.fn(),
    put: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
}));

import ConfigPage from "$routes-panel/admin/config/+page.svelte";
import { auth } from "../src/lib/stores/auth";

const admin = {
  id: "a1",
  email: "a@x.com",
  full_name: "Admin",
  is_active: true,
  chain_user_ref: "0x0",
  created_at: "2026-01-01T00:00:00Z",
  roles: ["admin"],
};

function cfg(over: Record<string, unknown> = {}) {
  return {
    env: "production",
    ai_provider: "openai",
    blockchain: "sepolia",
    dry_run: false,
    reward_ranks: [1, 2, 3],
    confirmations: 3,
    opc_max_reward_per_tx: 1000,
    rate_limit_enabled: true,
    csrf_enabled: true,
    readiness_check_redis: true,
    readiness_check_storage: true,
    use_local_storage: false,
    session_ttl_seconds: 86400,
    platform_timezone: "Asia/Jakarta",
    ...over,
  };
}

describe("admin config — sections, status banner, and formatting", () => {
  beforeEach(() => {
    cleanup();
    get.mockReset();
    auth.setUser(admin);
  });
  afterEach(() => auth.setUser(null));

  it("shows a production badge and the core-hardeners count", async () => {
    get.mockResolvedValue(cfg());
    render(ConfigPage);
    await waitFor(() => expect(screen.getByText(/Lingkungan: production/)).toBeTruthy());
    expect(document.querySelector('[data-role="env-banner"]')).toBeTruthy();
    // production + non-dry-run + rate-limit + csrf → 3/3 core safeguards.
    expect(screen.getByText(/3\/3 pengaman inti aktif/)).toBeTruthy();
  });

  it("flags a dry-run environment", async () => {
    get.mockResolvedValue(cfg({ env: "development", dry_run: true }));
    render(ConfigPage);
    await waitFor(() => expect(screen.getByText(/Mode non-produksi/)).toBeTruthy());
    expect(screen.getByText("Dry-run")).toBeTruthy();
  });

  it("formats the session TTL in human-readable units", async () => {
    get.mockResolvedValue(cfg({ session_ttl_seconds: 86400 }));
    render(ConfigPage);
    // Locale-independent: the day prefix shows for an 86400s TTL.
    await waitFor(() => expect(screen.getByText(/1 hari/)).toBeTruthy());
  });
});
