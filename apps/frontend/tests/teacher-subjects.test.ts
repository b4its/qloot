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

import TeacherSubjects from "$routes-panel/teacher/subjects/+page.svelte";
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

const subjects = [
  {
    id: "s1",
    title: "Fisika Dasar",
    slug: "fisika",
    owner_id: "t1",
    is_published: true,
    subject: "Fisika",
    class_code: "1A",
    class_type: "IPA",
    lesson_count: 4,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  },
  {
    id: "s2",
    title: "Matematika Draf",
    slug: "matematika",
    owner_id: "t1",
    is_published: false,
    subject: "Matematika",
    class_code: "2A",
    class_type: "IPA",
    lesson_count: 2,
    created_at: "2026-01-02T00:00:00Z",
    updated_at: "2026-01-02T00:00:00Z",
  },
];

describe("teacher subjects — metrics, search, and filters", () => {
  beforeEach(() => {
    cleanup();
    get.mockReset();
    auth.setUser(teacher);
    get.mockImplementation((path: string) =>
      path.startsWith("/courses") ? Promise.resolve(subjects) : Promise.resolve([]),
    );
  });
  afterEach(() => auth.setUser(null));

  it("renders the publish metrics", async () => {
    render(TeacherSubjects);
    await waitFor(() => expect(screen.getByText("Fisika Dasar")).toBeTruthy());
    // 1 published, 1 draft.
    expect(document.querySelector('[data-role="published-count"]')?.textContent?.trim()).toBe("1");
  });

  it("filters to drafts", async () => {
    render(TeacherSubjects);
    await waitFor(() => expect(screen.getByText("Fisika Dasar")).toBeTruthy());

    await fireEvent.click(screen.getByRole("button", { name: "Draf" }));
    await waitFor(() => expect(screen.queryByText("Fisika Dasar")).toBeNull());
    expect(screen.getByText("Matematika Draf")).toBeTruthy();
  });

  it("filters by class", async () => {
    render(TeacherSubjects);
    await waitFor(() => expect(screen.getByText("Fisika Dasar")).toBeTruthy());

    const select = screen.getByLabelText("Filter kelas") as HTMLSelectElement;
    await fireEvent.change(select, { target: { value: "2A" } });
    await waitFor(() => expect(screen.queryByText("Fisika Dasar")).toBeNull());
    expect(screen.getByText("Matematika Draf")).toBeTruthy();
  });

  it("searches subjects by title", async () => {
    render(TeacherSubjects);
    await waitFor(() => expect(screen.getByText("Fisika Dasar")).toBeTruthy());

    const input = screen.getByLabelText("Cari pelajaran") as HTMLInputElement;
    await fireEvent.input(input, { target: { value: "matematika" } });
    await waitFor(() => expect(screen.queryByText("Fisika Dasar")).toBeNull());
    expect(screen.getByText("Matematika Draf")).toBeTruthy();
  });
});
