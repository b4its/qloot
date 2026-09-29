// @vitest-environment jsdom
import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, fireEvent, cleanup, waitFor } from "@testing-library/svelte";

vi.mock("$app/navigation", () => ({ goto: vi.fn() }));

import BlogPage from "$routes-site/blog/+page.svelte";

beforeEach(() => cleanup());

describe("blog — category filter and search", () => {
  it("renders all posts with category chips", async () => {
    render(BlogPage);
    expect(screen.getByText("Cara menyusun jalur belajar yang realistis")).toBeTruthy();
    expect(screen.getByRole("button", { name: /Semua \(4\)/ })).toBeTruthy();
    expect(screen.getByRole("button", { name: /Panduan \(1\)/ })).toBeTruthy();
  });

  it("filters posts by category", async () => {
    render(BlogPage);
    await fireEvent.click(screen.getByRole("button", { name: /Desain \(1\)/ }));
    await waitFor(() =>
      expect(screen.queryByText("Cara menyusun jalur belajar yang realistis")).toBeNull(),
    );
    expect(screen.getByText("5 kesalahan umum saat membuat portofolio desain")).toBeTruthy();
  });

  it("searches posts by title and body", async () => {
    render(BlogPage);
    const input = screen.getByLabelText("Cari artikel") as HTMLInputElement;
    await fireEvent.input(input, { target: { value: "portofolio" } });
    await waitFor(() =>
      expect(screen.queryByText("Cara menyusun jalur belajar yang realistis")).toBeNull(),
    );
    expect(screen.getByText("5 kesalahan umum saat membuat portofolio desain")).toBeTruthy();
  });

  it("shows an empty state with reset when nothing matches", async () => {
    render(BlogPage);
    const input = screen.getByLabelText("Cari artikel") as HTMLInputElement;
    await fireEvent.input(input, { target: { value: "zzz-no-match" } });
    await waitFor(() => expect(screen.getByText(/Tidak ada artikel yang cocok/)).toBeTruthy());
    expect(screen.getByRole("button", { name: "Reset Filter" })).toBeTruthy();
  });

  it("keeps the expanded article tied to the post after filtering", async () => {
    render(BlogPage);
    // Expand the first article (Panduan).
    const toggles = screen.getAllByRole("button", { name: /Baca selengkapnya/ });
    await fireEvent.click(toggles[0]);
    await waitFor(() =>
      expect(
        screen
          .getAllByRole("button", { name: /Tutup/ })
          .some((b) => b.closest("[data-post]")?.getAttribute("data-post")?.includes("jalur")),
      ).toBe(true),
    );

    // Filter to a different category: the Desain article becomes index 0 but was
    // never expanded, so nothing should be open.
    await fireEvent.click(screen.getByRole("button", { name: /Desain \(1\)/ }));
    await waitFor(() =>
      expect(screen.getByText("5 kesalahan umum saat membuat portofolio desain")).toBeTruthy(),
    );
    expect(screen.queryByRole("button", { name: /Tutup/ })).toBeNull();
    expect(screen.queryByText(/Mulai dari tujuan akhir/)).toBeNull();
  });
});
