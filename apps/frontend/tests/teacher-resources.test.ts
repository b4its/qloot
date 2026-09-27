// @vitest-environment jsdom
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, fireEvent, cleanup, waitFor } from "@testing-library/svelte";

vi.mock("$app/navigation", () => ({ goto: vi.fn() }));

const get = vi.fn();
const del = vi.fn();
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
    delete: (...a: unknown[]) => del(...a),
  },
}));

import TeacherResources from "$routes-panel/teacher/resources/+page.svelte";
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

const resources = [
  { code: "c1", category: "course", title: "Kursus A", provider: "P", is_free: true, tags: [] },
  {
    code: "c2",
    category: "material",
    title: "Materi B",
    provider: "P",
    is_free: true,
    tags: [],
  },
];

describe("teacher resources — metrics, category chips, search, delete confirm", () => {
  beforeEach(() => {
    cleanup();
    get.mockReset();
    del.mockReset();
    auth.setUser(teacher);
    get.mockResolvedValue(resources);
    del.mockResolvedValue({});
  });
  afterEach(() => auth.setUser(null));

  it("renders category metrics", async () => {
    render(TeacherResources);
    await waitFor(() => expect(screen.getByText("Kursus A")).toBeTruthy());
    expect(document.querySelector('[data-role="total-count"]')?.textContent?.trim()).toBe("2");
  });

  it("filters by category via a chip", async () => {
    render(TeacherResources);
    await waitFor(() => expect(screen.getByText("Kursus A")).toBeTruthy());

    await fireEvent.click(screen.getByRole("button", { name: "Materi" }));
    await waitFor(() =>
      expect(get.mock.calls.some((c) => String(c[0]).includes("category=material"))).toBe(true),
    );
  });

  it("confirms before deleting a resource", async () => {
    render(TeacherResources);
    await waitFor(() => expect(screen.getByText("Kursus A")).toBeTruthy());

    const delButtons = screen.getAllByRole("button", { name: "Hapus sumber daya" });
    await fireEvent.click(delButtons[0]);
    expect(screen.getByText("Hapus Sumber Daya")).toBeTruthy();
    expect(del).not.toHaveBeenCalled();

    const confirm = document.querySelector(
      '[data-role="confirm-delete-resource"]',
    ) as HTMLButtonElement;
    await fireEvent.click(confirm);
    await waitFor(() => expect(del).toHaveBeenCalledWith("/career/resources/c1"));
  });
});
