// @vitest-environment jsdom
import { describe, it, expect } from "vitest";
import { render, screen, cleanup, fireEvent } from "@testing-library/svelte";

import Skeleton from "$lib/components/Skeleton.svelte";
import EmptyState from "$lib/components/EmptyState.svelte";
import consultationSrc from "$routes-site/career/consultation/+page.svelte?raw";
import roadmapSrc from "$routes-site/career/roadmap/+page.svelte?raw";
import librarySrc from "$routes-site/career/library/+page.svelte?raw";
import assistantSrc from "$routes-site/assistant/+page.svelte?raw";

describe("shared loading/empty components (UIX-03)", () => {
  it("Skeleton renders a polite status region", () => {
    cleanup();
    render(Skeleton, { props: { rows: 3 } });
    const status = screen.getByRole("status");
    expect(status.getAttribute("aria-live")).toBe("polite");
  });

  it("EmptyState renders a title and action", () => {
    cleanup();
    render(EmptyState, {
      props: { title: "Belum ada data", actionHref: "/x", actionLabel: "Tambah" },
    });
    expect(screen.getByText("Belum ada data")).toBeTruthy();
    expect(screen.getByText("Tambah")).toBeTruthy();
  });

  it("EmptyState supports an in-page action callback", async () => {
    cleanup();
    let clicked = 0;
    render(EmptyState, {
      props: { title: "Kosong", actionLabel: "Coba lagi", onAction: () => (clicked += 1) },
    });
    await fireEvent.click(screen.getByRole("button", { name: /Coba lagi/ }));
    expect(clicked).toBe(1);
  });

  it("no career page uses the bare 'Memuat …' text anymore", () => {
    for (const src of [consultationSrc, roadmapSrc, librarySrc, assistantSrc]) {
      expect(src).not.toContain(">Memuat …<");
    }
  });

  it("career pages use the shared Skeleton", () => {
    for (const src of [consultationSrc, roadmapSrc, librarySrc]) {
      expect(src).toContain("Skeleton");
    }
  });
});
