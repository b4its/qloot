// @vitest-environment jsdom
import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, cleanup, waitFor } from "@testing-library/svelte";

vi.mock("$app/stores", () => ({
  page: {
    subscribe: (fn: (v: unknown) => void) => (
      fn({ params: { credentialId: "CRED-1" }, url: new URL("http://x/verify/CRED-1") }),
      () => {}
    ),
  },
}));

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

import VerifyPage from "$routes-site/verify/[credentialId]/+page.svelte";

async function run(over: Record<string, unknown>) {
  get.mockResolvedValue({
    valid: true,
    credential_id: "CRED-1",
    course_title: "Fisika Dasar",
    recipient_name: "Andi",
    issued_by: "QLoot",
    issued_at: "2026-01-01T00:00:00Z",
    verification_hash: "0xabc",
    anchor_status: "none",
    ...over,
  });
  render(VerifyPage);
}

beforeEach(() => {
  cleanup();
  get.mockReset();
});

describe("verify credential page — trust banner and checklist", () => {
  it("shows a valid trust banner with the check timestamp", async () => {
    await run({});
    await waitFor(() => expect(screen.getByText(/Kredensial valid/)).toBeTruthy());
    expect(screen.getByText(/Diverifikasi QLoot/)).toBeTruthy();
    expect(screen.getByText("Andi")).toBeTruthy();
  });

  it("renders the verification checklist with per-item results", async () => {
    await run({ anchor_status: "anchored", anchor_tx_hash: "0xdead" });
    await waitFor(() => expect(screen.getByText("Hasil pemeriksaan")).toBeTruthy());
    expect(screen.getByText("Kredensial terdaftar & tidak dicabut")).toBeTruthy();
    expect(screen.getByText("Hash verifikasi tersedia")).toBeTruthy();
    expect(screen.getByText("Sudah di-anchor on-chain (QTC)")).toBeTruthy();
    // Anchored → the "On-chain" badge shows.
    expect(screen.getByText("On-chain")).toBeTruthy();
  });

  it("shows an invalid state when the credential is not valid", async () => {
    await run({ valid: false });
    await waitFor(() =>
      expect(screen.getByText(/tidak ditemukan atau sudah dicabut/)).toBeTruthy(),
    );
    expect(screen.queryByText("Hasil pemeriksaan")).toBeNull();
  });
});
