// @vitest-environment jsdom
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, fireEvent, cleanup, waitFor } from "@testing-library/svelte";

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

import MaterialsListPage from "$routes-panel/teacher/materials/+page.svelte";
import { auth } from "../src/lib/stores/auth";

const teacher = {
  id: "t1",
  email: "t@x.com",
  full_name: "Teacher",
  is_active: true,
  chain_user_ref: "0x0",
  created_at: "2026-01-01T00:00:00Z",
  roles: ["teacher"],
};

function mat(over: Record<string, unknown> = {}) {
  return {
    id: "m1",
    owner_id: "t1",
    filename: "Fisika.pdf",
    content_type: "application/pdf",
    size_bytes: 1_048_576, // 1 MB
    status: "ready",
    extraction_status: "ok",
    created_at: "2026-01-01T00:00:00Z",
    ...over,
  };
}

const materials = [
  mat({ id: "m1", filename: "Fisika.pdf" }),
  mat({ id: "m2", filename: "Kimia-scan.pdf", extraction_status: "ocr" }),
  mat({ id: "m3", filename: "Biologi-kosong.pdf", status: "uploaded", extraction_status: "empty" }),
];

describe("teacher materials list — metrics, filters, and size", () => {
  beforeEach(() => {
    cleanup();
    get.mockReset();
    auth.setUser(teacher);
    get.mockImplementation((path: string) =>
      path.startsWith("/materials") ? Promise.resolve(materials) : Promise.resolve([]),
    );
  });
  afterEach(() => auth.setUser(null));

  it("renders the extraction-quality metrics", async () => {
    render(MaterialsListPage);
    await waitFor(() => expect(screen.getByText("Fisika.pdf")).toBeTruthy());
    // ready count = 2 (ok + ocr rows have status ready), OCR = 1, empty = 1.
    expect(document.querySelector('[data-role="ready-count"]')?.textContent?.trim()).toBe("2");
    // The OCR metric card and the OCR quality chip both render.
    expect(screen.getAllByText("Hasil OCR").length).toBeGreaterThan(0);
  });

  it("formats the file size in human units", async () => {
    render(MaterialsListPage);
    await waitFor(() => expect(screen.getByText("Fisika.pdf")).toBeTruthy());
    expect(screen.getAllByText("1.0 MB").length).toBeGreaterThan(0);
  });

  it("filters by extraction quality", async () => {
    render(MaterialsListPage);
    await waitFor(() => expect(screen.getByText("Fisika.pdf")).toBeTruthy());

    const select = screen.getByLabelText("Filter kualitas") as HTMLSelectElement;
    await fireEvent.change(select, { target: { value: "empty" } });
    await waitFor(() => expect(screen.queryByText("Fisika.pdf")).toBeNull());
    expect(screen.getByText("Biologi-kosong.pdf")).toBeTruthy();
  });

  it("searches materials by filename", async () => {
    render(MaterialsListPage);
    await waitFor(() => expect(screen.getByText("Fisika.pdf")).toBeTruthy());

    const input = screen.getByLabelText("Cari materi") as HTMLInputElement;
    await fireEvent.input(input, { target: { value: "kimia" } });
    await waitFor(() => expect(screen.queryByText("Fisika.pdf")).toBeNull());
    expect(screen.getByText("Kimia-scan.pdf")).toBeTruthy();
  });
});
