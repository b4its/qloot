// @vitest-environment jsdom
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, fireEvent, cleanup, waitFor } from "@testing-library/svelte";

vi.mock("$app/stores", () => ({
  page: {
    subscribe: (fn: (v: unknown) => void) => (
      fn({ params: { id: "ex1" }, url: new URL("http://x/teacher/exams/ex1") }),
      () => {}
    ),
  },
}));
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

import { auth } from "$lib/stores/auth";
import TeacherExamPage from "$routes-panel/teacher/exams/[id]/+page.svelte";

const teacher = {
  id: "t1",
  email: "teacher@test.com",
  full_name: "Guru Test",
  roles: ["teacher"],
  is_active: true,
  chain_user_ref: "0x0",
  created_at: "2026-01-01T00:00:00Z",
};

const sampleExam = {
  id: "ex1",
  title: "Ujian Biologi",
  owner_id: "t1",
  duration_minutes: 45,
  passing_score_bp: 6000,
  is_active: false,
  questions: [],
};

describe("teacher exam — multiple-choice option editor reactivity", () => {
  beforeEach(() => {
    cleanup();
    get.mockReset();
    auth.setUser(teacher);
    get.mockImplementation((path: string) => {
      if (path === "/exams/ex1") return Promise.resolve(sampleExam);
      if (path === "/exams/ex1/questions") return Promise.resolve([]);
      return Promise.resolve([]);
    });
  });

  afterEach(() => auth.setUser(null));

  it("adds and removes option rows when the buttons are clicked", async () => {
    render(TeacherExamPage);
    await waitFor(() => expect(screen.getByText("Ujian Biologi")).toBeTruthy());

    // Switch the new-question draft to multiple choice.
    const typeSelect = screen.getByDisplayValue("Esai (dinilai AI)") as HTMLSelectElement;
    await fireEvent.change(typeSelect, { target: { value: "multiple_choice" } });

    // Two blank option rows are rendered by default (A and B).
    await waitFor(() => {
      expect(screen.getAllByPlaceholderText("Teks pilihan").length).toBe(2);
    });

    const addBtn = screen.getByText("Tambah pilihan");
    await fireEvent.click(addBtn);
    await waitFor(() => {
      expect(screen.getAllByPlaceholderText("Teks pilihan").length).toBe(3);
    });

    await fireEvent.click(addBtn);
    await waitFor(() => {
      expect(screen.getAllByPlaceholderText("Teks pilihan").length).toBe(4);
    });

    // Remove the last row.
    const removeButtons = screen.getAllByLabelText("Hapus pilihan");
    await fireEvent.click(removeButtons[3]);
    await waitFor(() => {
      expect(screen.getAllByPlaceholderText("Teks pilihan").length).toBe(3);
    });
  });

  it("moves the correct-answer marker when a different option is picked", async () => {
    render(TeacherExamPage);
    await waitFor(() => expect(screen.getByText("Ujian Biologi")).toBeTruthy());

    const typeSelect = screen.getByDisplayValue("Esai (dinilai AI)") as HTMLSelectElement;
    await fireEvent.change(typeSelect, { target: { value: "multiple_choice" } });
    await waitFor(() => {
      expect(screen.getAllByPlaceholderText("Teks pilihan").length).toBe(2);
    });

    const markers = () => screen.getAllByLabelText(/Tandai opsi .* sebagai jawaban benar/);
    // Option A is correct by default.
    expect(markers()[0].getAttribute("aria-pressed")).toBe("true");
    expect(markers()[1].getAttribute("aria-pressed")).toBe("false");

    await fireEvent.click(markers()[1]);
    await waitFor(() => {
      expect(markers()[0].getAttribute("aria-pressed")).toBe("false");
      expect(markers()[1].getAttribute("aria-pressed")).toBe("true");
    });
  });
});
