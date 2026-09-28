// @vitest-environment jsdom
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, fireEvent, cleanup, waitFor } from "@testing-library/svelte";

const get = vi.fn();
const { post } = vi.hoisted(() => ({ post: vi.fn() }));
vi.mock("../src/lib/api/client", () => ({
  API_BASE: "http://localhost:8000",
  ApiError: class ApiError extends Error {
    status = 0;
  },
  api: {
    get: (...a: unknown[]) => get(...a),
    post: (...a: unknown[]) => post(...a),
    put: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
}));

import CertificatesPage from "$routes-site/certificates/+page.svelte";
import { auth } from "../src/lib/stores/auth";

function cert(over: Record<string, unknown> = {}) {
  return {
    id: "c1",
    credential_id: "CRED-1",
    verification_hash: "0xabc",
    course_id: "co1",
    course_title: "Fisika Dasar",
    recipient_name: "Student",
    issued_by: "QLoot",
    edition_number: 1,
    edition_total: 10,
    issued_at: "2026-01-01T00:00:00Z",
    revoked_at: null,
    revoked_reason: null,
    anchor_status: "none",
    anchor_tx_hash: null,
    anchored_at: null,
    ...over,
  };
}

const certs = [
  cert({ id: "c1", credential_id: "CRED-1", course_title: "Fisika Dasar" }),
  cert({
    id: "c2",
    credential_id: "CRED-2",
    course_title: "Matematika Lanjut",
    anchor_status: "anchored",
    anchor_tx_hash: "0xdead",
  }),
  cert({
    id: "c3",
    credential_id: "CRED-3",
    course_title: "Kimia Organik",
    revoked_at: "2026-02-01T00:00:00Z",
  }),
];

/** The "other certificates" list items carry a chevron-right icon. */
function listTitles(): string[] {
  const list = document.querySelectorAll("aside ul li button span.min-w-0 > span:first-child");
  return Array.from(list).map((el) => el.textContent?.trim() ?? "");
}

describe("certificates page — metrics, search, and status filter", () => {
  beforeEach(() => {
    cleanup();
    get.mockReset();
    auth.setUser({
      id: "u1",
      email: "s@x.com",
      full_name: "Student",
      is_active: true,
      chain_user_ref: "0x0",
      created_at: "2026-01-01T00:00:00Z",
      roles: ["student"],
    });
    get.mockImplementation((path: string) =>
      path.startsWith("/certificates") ? Promise.resolve(certs) : Promise.resolve([]),
    );
  });
  afterEach(() => auth.setUser(null));

  it("shows the status metric strip", async () => {
    render(CertificatesPage);
    await waitFor(() => expect(screen.getAllByText("Fisika Dasar").length).toBeGreaterThan(0));
    // 3 total, 2 active (1 revoked), 1 anchored.
    expect(document.querySelector('[data-role="active-count"]')?.textContent?.trim()).toBe("2");
    // The "On-chain" metric card and the list badge both render.
    expect(screen.getAllByText("On-chain").length).toBeGreaterThan(0);
  });

  it("filters the list to revoked certificates", async () => {
    render(CertificatesPage);
    await waitFor(() => expect(listTitles().length).toBeGreaterThan(0));

    // The filter chip is a plain button (the list status is a span).
    const chip = screen
      .getAllByRole("button", { name: "Dicabut" })
      .find((b) => b.classList.contains("badge"));
    await fireEvent.click(chip!);
    await waitFor(() => {
      const titles = listTitles();
      expect(titles).toContain("Kimia Organik");
      expect(titles).not.toContain("Matematika Lanjut");
      expect(titles).not.toContain("Fisika Dasar");
    });
  });

  it("searches certificates by course title", async () => {
    render(CertificatesPage);
    await waitFor(() => expect(listTitles().length).toBeGreaterThan(0));

    const input = screen.getByLabelText("Cari sertifikat") as HTMLInputElement;
    await fireEvent.input(input, { target: { value: "matematika" } });
    await waitFor(() => {
      const titles = listTitles();
      expect(titles).toContain("Matematika Lanjut");
      expect(titles).not.toContain("Kimia Organik");
    });
  });

  it("offers a retry button when anchoring failed", async () => {
    post.mockResolvedValue({});
    const failed = [
      cert({
        id: "cf",
        credential_id: "CRED-F",
        course_title: "Gagal Anchor",
        anchor_status: "failed",
      }),
    ];
    get.mockImplementation((path: string) =>
      path.startsWith("/certificates") ? Promise.resolve(failed) : Promise.resolve([]),
    );
    render(CertificatesPage);
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /Coba anchor lagi/ })).toBeTruthy(),
    );

    await fireEvent.click(screen.getByRole("button", { name: /Coba anchor lagi/ }));
    await waitFor(() => expect(post).toHaveBeenCalledWith("/certificates/CRED-F/anchor"));
  });

  it("reports a copy failure instead of silently doing nothing", async () => {
    // Simulate a denied clipboard write.
    Object.assign(navigator, {
      clipboard: { writeText: vi.fn().mockRejectedValue(new Error("denied")) },
    });
    render(CertificatesPage);
    await waitFor(() => expect(screen.getByRole("button", { name: /Salin tautan/ })).toBeTruthy());

    await fireEvent.click(screen.getByRole("button", { name: /Salin tautan/ }));
    expect(await screen.findByText(/gagal menyalin tautan/i)).toBeTruthy();
  });
});
