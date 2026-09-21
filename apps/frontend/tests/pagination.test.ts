// @vitest-environment jsdom
import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/svelte";

// The component only imports the Icon wrapper (no network).
vi.mock("../src/lib/api/client", () => ({
  API_BASE: "http://localhost:8000",
  ApiError: class ApiError extends Error {
    status = 0;
  },
  api: { get: vi.fn(), post: vi.fn(), put: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}));

import Pagination from "$lib/components/Pagination.svelte";

describe("Pagination", () => {
  beforeEach(() => cleanup());

  it("renders nothing when there is a single page (total mode)", () => {
    const { container } = render(Pagination, { page: 1, pageSize: 20, total: 5 });
    expect(container.querySelector("button")).toBeNull();
  });

  it("shows the range and page count with a total", () => {
    render(Pagination, { page: 2, pageSize: 20, total: 95 });
    expect(screen.getByText(/21–40 dari 95/)).toBeTruthy();
    expect(screen.getByText(/Hal\. 2\/5/)).toBeTruthy();
  });

  it("disables Previous on the first page and Next on the last", () => {
    render(Pagination, { page: 1, pageSize: 20, total: 40 });
    expect(screen.getByRole("button", { name: /sebelumnya/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /berikutnya/i })).not.toBeDisabled();
    cleanup();

    render(Pagination, { page: 2, pageSize: 20, total: 40 });
    expect(screen.getByRole("button", { name: /berikutnya/i })).toBeDisabled();
  });

  it("invokes onPrev and onNext callbacks", async () => {
    const onPrev = vi.fn();
    const onNext = vi.fn();
    render(Pagination, { page: 2, pageSize: 20, total: 60, onPrev, onNext });

    await fireEvent.click(screen.getByRole("button", { name: /sebelumnya/i }));
    await fireEvent.click(screen.getByRole("button", { name: /berikutnya/i }));
    expect(onPrev).toHaveBeenCalledOnce();
    expect(onNext).toHaveBeenCalledOnce();
  });

  it("supports cursor mode via hasMore", () => {
    render(Pagination, { page: 1, pageSize: 20, hasMore: false });
    expect(screen.getByRole("button", { name: /berikutnya/i })).toBeDisabled();
  });

  it("disables both buttons while loading", () => {
    render(Pagination, { page: 2, pageSize: 20, total: 100, loading: true });
    expect(screen.getByRole("button", { name: /sebelumnya/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /berikutnya/i })).toBeDisabled();
  });
});
