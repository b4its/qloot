// @vitest-environment jsdom
import { describe, it, expect, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/svelte";

import ProgressRing from "$lib/components/ProgressRing.svelte";

describe("ProgressRing", () => {
  afterEach(() => cleanup());

  it("exposes progressbar semantics", () => {
    cleanup();
    render(ProgressRing, { props: { value: 42, label: "Rata-rata" } });
    const bar = screen.getByRole("progressbar", { name: "Rata-rata: 42%" });
    expect(bar.getAttribute("aria-valuenow")).toBe("42");
  });

  it("uses a unique gradient id per instance (no duplicate DOM ids)", () => {
    cleanup();
    render(ProgressRing, { props: { value: 10 } });
    render(ProgressRing, { props: { value: 20 } });
    const ids = Array.from(document.querySelectorAll("linearGradient")).map((g) => g.id);
    expect(ids.length).toBe(2);
    expect(new Set(ids).size).toBe(2);
  });
});
