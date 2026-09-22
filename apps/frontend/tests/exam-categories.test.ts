// @vitest-environment jsdom
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/svelte";

// The page reads $page.url / $page.params and navigates on click.
vi.mock("$app/stores", () => ({
  page: {
    subscribe: (fn: (v: unknown) => void) => (
      fn({ params: {}, url: new URL("http://x/exams") }),
      () => {}
    ),
  },
}));
vi.mock("$app/navigation", () => ({ goto: vi.fn() }));

vi.mock("../src/lib/api/client", () => ({
  API_BASE: "http://localhost:8000",
  ApiError: class ApiError extends Error {
    status = 0;
  },
  api: { get: vi.fn(), post: vi.fn(), put: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}));

import { api } from "$lib/api/client";
import { auth } from "$lib/stores/auth";
import ExamsPage from "../src/routes/(site)/exams/+page.svelte";

const exams = [
  {
    id: "mc1",
    title: "Kuis PG",
    owner_id: "t1",
    duration_minutes: 15,
    status: "published",
    is_active: true,
    passing_score_bp: 6000,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    question_count: 5,
    mc_count: 5,
    essay_count: 0,
  },
  {
    id: "essay1",
    title: "Ujian Esai",
    owner_id: "t1",
    duration_minutes: 60,
    status: "published",
    is_active: true,
    passing_score_bp: 6000,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    question_count: 3,
    mc_count: 0,
    essay_count: 3,
  },
  {
    id: "mix1",
    title: "Ujian Campuran",
    owner_id: "t1",
    duration_minutes: 30,
    status: "published",
    is_active: true,
    passing_score_bp: 6000,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    question_count: 4,
    mc_count: 2,
    essay_count: 2,
  },
];

describe("student exams page — multiple-choice vs essay split", () => {
  beforeEach(() => {
    cleanup();
    auth.setUser(null);
    (api.get as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(exams);
  });
  afterEach(() => auth.setUser(null));

  it("renders Pilihan Ganda and Esai category tabs with counts", async () => {
    render(ExamsPage, {});
    expect(await screen.findByRole("tab", { name: /pilihan ganda/i })).toBeTruthy();
    expect(screen.getByRole("tab", { name: /esai/i })).toBeTruthy();
    expect(screen.getByRole("tab", { name: /semua/i })).toBeTruthy();
  });

  it("groups exams into labelled sections under Semua", async () => {
    render(ExamsPage, {});
    // Section headings mirror the categories.
    expect(await screen.findByRole("heading", { name: /pilihan ganda/i })).toBeTruthy();
    expect(screen.getByRole("heading", { name: /^esai/i })).toBeTruthy();
    // Every exam is present in the default (all) view.
    expect(screen.getByText("Kuis PG")).toBeTruthy();
    expect(screen.getByText("Ujian Esai")).toBeTruthy();
    expect(screen.getByText("Ujian Campuran")).toBeTruthy();
  });

  it("filters to only multiple-choice exams when the PG tab is clicked", async () => {
    render(ExamsPage, {});
    await fireEvent.click(await screen.findByRole("tab", { name: /pilihan ganda/i }));
    expect(screen.getByText("Kuis PG")).toBeTruthy();
    expect(screen.queryByText("Ujian Esai")).toBeNull();
    expect(screen.queryByText("Ujian Campuran")).toBeNull();
  });

  it("filters to only essay exams when the Esai tab is clicked", async () => {
    render(ExamsPage, {});
    await fireEvent.click(await screen.findByRole("tab", { name: /esai/i }));
    expect(screen.getByText("Ujian Esai")).toBeTruthy();
    expect(screen.queryByText("Kuis PG")).toBeNull();
    expect(screen.queryByText("Ujian Campuran")).toBeNull();
  });

  it("shows mixed exams under the Campuran tab", async () => {
    render(ExamsPage, {});
    await fireEvent.click(await screen.findByRole("tab", { name: /campuran/i }));
    expect(screen.getByText("Ujian Campuran")).toBeTruthy();
    expect(screen.queryByText("Kuis PG")).toBeNull();
    expect(screen.queryByText("Ujian Esai")).toBeNull();
  });
});
