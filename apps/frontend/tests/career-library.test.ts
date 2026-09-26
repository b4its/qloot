// @vitest-environment jsdom
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, fireEvent, cleanup, waitFor } from "@testing-library/svelte";

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

import LibraryPage from "$routes-site/career/library/+page.svelte";

const resources = [
  {
    code: "c1",
    category: "course",
    title: "Kalkulus Dasar",
    description: "d",
    provider: "Coursera",
    is_free: true,
    tags: ["matematika"],
  },
  {
    code: "c2",
    category: "course",
    title: "Fisika Lanjut",
    description: "d",
    provider: "edX",
    is_free: false,
    tags: ["fisika"],
  },
  {
    code: "c3",
    category: "course",
    title: "Biologi Sel",
    description: "d",
    provider: "Coursera",
    is_free: true,
    tags: ["biologi"],
  },
];

describe("career library — metrics, cost filter, provider filter, sort", () => {
  beforeEach(() => {
    cleanup();
    get.mockReset();
    get.mockImplementation((path: string) => {
      if (path.startsWith("/career/recommendations")) return Promise.resolve([]);
      if (path.startsWith("/career/resources")) return Promise.resolve(resources);
      return Promise.resolve([]);
    });
  });
  afterEach(() => cleanup());

  it("renders the free/paid metrics", async () => {
    render(LibraryPage);
    await waitFor(() => expect(screen.getByText("Kalkulus Dasar")).toBeTruthy());
    expect(document.querySelector('[data-role="total-count"]')?.textContent?.trim()).toBe("3");
    expect(document.querySelector('[data-role="free-count"]')?.textContent?.trim()).toBe("2");
  });

  it("filters to free resources only", async () => {
    render(LibraryPage);
    await waitFor(() => expect(screen.getByText("Kalkulus Dasar")).toBeTruthy());

    await fireEvent.click(screen.getByRole("button", { name: "Gratis" }));
    await waitFor(() => expect(screen.queryByText("Fisika Lanjut")).toBeNull());
    expect(screen.getByText("Kalkulus Dasar")).toBeTruthy();
    expect(screen.getByText("Biologi Sel")).toBeTruthy();
  });

  it("filters by provider", async () => {
    render(LibraryPage);
    await waitFor(() => expect(screen.getByText("Kalkulus Dasar")).toBeTruthy());

    const select = screen.getByLabelText("Filter penyedia") as HTMLSelectElement;
    await fireEvent.change(select, { target: { value: "Coursera" } });
    await waitFor(() => expect(screen.queryByText("Fisika Lanjut")).toBeNull());
    expect(screen.getByText("Kalkulus Dasar")).toBeTruthy();
  });

  it("sorts by title A–Z", async () => {
    render(LibraryPage);
    await waitFor(() => expect(screen.getByText("Kalkulus Dasar")).toBeTruthy());

    const headings = screen.getAllByRole("heading", { level: 2 }).map((h) => h.textContent);
    // Sorted: Biologi Sel, Fisika Lanjut, Kalkulus Dasar.
    expect(headings[0]).toBe("Biologi Sel");
    expect(headings[2]).toBe("Kalkulus Dasar");
  });
});
