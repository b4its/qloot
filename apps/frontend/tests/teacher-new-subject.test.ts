// @vitest-environment jsdom
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, fireEvent, cleanup, waitFor } from "@testing-library/svelte";

const goto = vi.fn();
vi.mock("$app/navigation", () => ({ goto: (...a: unknown[]) => goto(...a) }));

const post = vi.fn();
vi.mock("../src/lib/api/client", () => ({
  API_BASE: "http://localhost:8000",
  ApiError: class ApiError extends Error {
    status = 0;
  },
  api: {
    get: vi.fn(),
    post: (...a: unknown[]) => post(...a),
    put: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
}));

import NewSubjectPage from "$routes-panel/teacher/subjects/new/+page.svelte";
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

describe("teacher new-subject form — preview, validation, and submit", () => {
  beforeEach(() => {
    cleanup();
    post.mockReset();
    goto.mockReset();
    auth.setUser(teacher);
    post.mockResolvedValue({ id: "c1", title: "Matematika 1A" });
  });
  afterEach(() => auth.setUser(null));

  it("keeps submit disabled until the title and class are filled", async () => {
    render(NewSubjectPage);
    const submit = screen.getByRole("button", { name: /Buat pelajaran/i }) as HTMLButtonElement;
    expect(submit.disabled).toBe(true);

    await fireEvent.input(screen.getByPlaceholderText("mis. Matematika 1A"), {
      target: { value: "Aljabar" },
    });
    // Class defaults to 1A, so a title alone enables submit.
    await waitFor(() => expect(submit.disabled).toBe(false));
  });

  it("updates the live preview as fields change", async () => {
    render(NewSubjectPage);
    await fireEvent.input(screen.getByPlaceholderText("mis. Matematika 1A"), {
      target: { value: "Fisika Kuantum" },
    });
    // The preview heading mirrors the entered title.
    await waitFor(() => expect(screen.getByText("Fisika Kuantum")).toBeTruthy());
    expect(screen.getAllByText(/Siswa di kelas/).length).toBeGreaterThan(0);
  });

  it("offers subject suggestions via a datalist", async () => {
    render(NewSubjectPage);
    expect(document.querySelector("#subject-suggestions")).toBeTruthy();
  });

  it("posts the payload and redirects on submit", async () => {
    render(NewSubjectPage);
    await fireEvent.input(screen.getByPlaceholderText("mis. Matematika 1A"), {
      target: { value: "Matematika 1A" },
    });
    const submit = screen.getByRole("button", { name: /Buat pelajaran/i }) as HTMLButtonElement;
    await waitFor(() => expect(submit.disabled).toBe(false));
    await fireEvent.click(submit);

    await waitFor(() =>
      expect(post).toHaveBeenCalledWith(
        "/courses",
        expect.objectContaining({ title: "Matematika 1A", class_code: "1A" }),
      ),
    );
    await waitFor(() => expect(goto).toHaveBeenCalledWith("/teacher/subjects/c1"));
  });
});
