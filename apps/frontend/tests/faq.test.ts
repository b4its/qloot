// @vitest-environment jsdom
import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, fireEvent, cleanup, waitFor } from "@testing-library/svelte";

vi.mock("$app/navigation", () => ({ goto: vi.fn() }));

import FaqPage from "$routes-site/faq/+page.svelte";

beforeEach(() => cleanup());

describe("faq — search", () => {
  it("renders the questions", async () => {
    render(FaqPage);
    expect(screen.getByText("Apakah sertifikatnya diakui?")).toBeTruthy();
    expect(screen.getByText("Apakah ada komunitas?")).toBeTruthy();
  });

  it("filters questions by keyword", async () => {
    render(FaqPage);
    const input = screen.getByLabelText("Cari pertanyaan") as HTMLInputElement;
    await fireEvent.input(input, { target: { value: "sertifikat" } });
    await waitFor(() => expect(screen.queryByText("Apakah ada komunitas?")).toBeNull());
    expect(screen.getByText("Apakah sertifikatnya diakui?")).toBeTruthy();
  });

  it("matches against the answer text too", async () => {
    render(FaqPage);
    const input = screen.getByLabelText("Cari pertanyaan") as HTMLInputElement;
    await fireEvent.input(input, { target: { value: "komunitas" } });
    await waitFor(() => expect(screen.queryByText("Apakah sertifikatnya diakui?")).toBeNull());
    expect(screen.getByText("Apakah ada komunitas?")).toBeTruthy();
  });

  it("shows a no-results state with a community CTA", async () => {
    render(FaqPage);
    const input = screen.getByLabelText("Cari pertanyaan") as HTMLInputElement;
    await fireEvent.input(input, { target: { value: "zzz-no-match" } });
    await waitFor(() => expect(screen.getByText("Tidak ada pertanyaan yang cocok")).toBeTruthy());
    expect(screen.getAllByRole("link", { name: /Tanya di komunitas/ }).length).toBeGreaterThan(0);
  });
});
