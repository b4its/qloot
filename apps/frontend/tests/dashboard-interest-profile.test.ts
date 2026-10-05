// @vitest-environment jsdom
import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, cleanup, waitFor, screen } from "@testing-library/svelte";

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

import DashboardPage from "$routes-site/dashboard/+page.svelte";
import dashboardSrc from "$routes-site/dashboard/+page.svelte?raw";
import { auth } from "../src/lib/stores/auth";

const mockAcademic = {
  term: "2025/2026-genap",
  grades: [],
  insights: [
    {
      kind: "consistency",
      title: "Fisika konsisten kuat",
      detail: "Nilai Fisika tertinggi (92). Pertahankan.",
    },
    {
      kind: "attention",
      title: "Kimia perlu perhatian",
      detail: "Nilai Kimia terendah (64). Fokus penguatan.",
    },
    {
      kind: "potential",
      title: "Proyeksi rumpun studi",
      detail: "Kekuatan pada Fisika mengarah ke rumpun teknik & sains.",
    },
  ],
  radar: [
    { dimension: "Seni", value: 50 },
    { dimension: "Teknik", value: 88 },
    { dimension: "Bahasa", value: 83 },
    { dimension: "Sains", value: 78 },
    { dimension: "Bisnis", value: 85 },
    { dimension: "Sosial", value: 88 },
  ],
  trend: [],
};

describe("dashboard interest profile (profil minat) & academic insights aesthetic cards", () => {
  beforeEach(() => {
    cleanup();
    get.mockReset();
    auth.setUser({
      id: "u_student",
      email: "student@x.com",
      full_name: "Student User",
      is_active: true,
      chain_user_ref: "0x0",
      created_at: "2026-01-01T00:00:00Z",
      roles: ["student"],
    });
    get.mockImplementation((path: string) => {
      if (path === "/career/dashboard") return Promise.resolve(mockAcademic);
      if (path === "/career/grades") return Promise.resolve([]);
      return Promise.resolve([]);
    });
  });

  it("contains logic for sorting radar descending and rich card metadata in source", () => {
    expect(dashboardSrc).toContain("sortedRadar");
    expect(dashboardSrc).toContain("b.value - a.value");
    expect(dashboardSrc).toContain("INTEREST_METADATA");
    expect(dashboardSrc).toContain("interestTier");
    expect(dashboardSrc).toContain('data-role="interest-profile"');
    expect(dashboardSrc).toContain("Profil Minat & Bakat");
    expect(dashboardSrc).toContain("insightMeta");
    expect(dashboardSrc).toContain('data-role="academic-insights"');
  });

  it("renders interest profile sorted by highest score first and displays Top 1 badge", async () => {
    render(DashboardPage);

    await waitFor(() => {
      expect(screen.getByText("Profil Minat & Bakat")).toBeTruthy();
    });

    // Check all dimensions rendered
    expect(screen.getByText("Teknik")).toBeTruthy();
    expect(screen.getByText("Sosial")).toBeTruthy();
    expect(screen.getByText("Bisnis")).toBeTruthy();
    expect(screen.getByText("Bahasa")).toBeTruthy();
    expect(screen.getByText("Sains")).toBeTruthy();
    expect(screen.getByText("Seni")).toBeTruthy();

    // Verify ordering in DOM: first card must be the highest score (Teknik or Sosial with 88)
    const cards = document.querySelectorAll('[data-role="interest-profile"] [data-dimension]');
    expect(cards.length).toBe(6);

    const firstDimension = cards[0].getAttribute("data-dimension");
    const secondDimension = cards[1].getAttribute("data-dimension");
    const lastDimension = cards[5].getAttribute("data-dimension");

    // Both Teknik and Sosial have 88, sorted alphabetically if tied
    expect(["Sosial", "Teknik"]).toContain(firstDimension);
    expect(["Sosial", "Teknik"]).toContain(secondDimension);
    // Seni is the lowest with 50
    expect(lastDimension).toBe("Seni");

    // Check presence of Top 1 badge
    expect(screen.getByText("Top 1")).toBeTruthy();

    // Check large score formatting
    const scoreElements = screen.getAllByText("88");
    expect(scoreElements.length).toBeGreaterThanOrEqual(1);
  });

  it("renders academic insights in modern aesthetic card grid", async () => {
    render(DashboardPage);

    await waitFor(() => {
      expect(screen.getByText("Wawasan & Evaluasi Akademik")).toBeTruthy();
    });

    expect(screen.getByText("Fisika konsisten kuat")).toBeTruthy();
    expect(screen.getByText("Kimia perlu perhatian")).toBeTruthy();
    expect(screen.getByText("Proyeksi rumpun studi")).toBeTruthy();

    expect(screen.getByText("Kekuatan Unggulan")).toBeTruthy();
    expect(screen.getByText("Area Penguatan")).toBeTruthy();
    expect(screen.getByText("Proyeksi Akademik & Karir")).toBeTruthy();

    const insightCards = document.querySelectorAll(
      '[data-role="academic-insights"] [data-insight]',
    );
    expect(insightCards.length).toBe(3);
  });
});
