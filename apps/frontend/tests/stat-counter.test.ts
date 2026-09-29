// @vitest-environment jsdom
import { describe, it, expect, afterEach } from "vitest";
import { render, screen, cleanup, waitFor } from "@testing-library/svelte";

import StatCounter from "$lib/components/StatCounter.svelte";

describe("StatCounter semantics", () => {
  afterEach(() => cleanup());

  it("exposes the final value as an accessible name while animating", () => {
    cleanup();
    render(StatCounter, { props: { value: 1234, suffix: "+" } });
    // The wrapping span carries the real value for assistive tech...
    const label = screen.getByLabelText("1.234+");
    expect(label).toBeTruthy();
    // ...while the animated digits are hidden from the a11y tree.
    expect(label.querySelector('[aria-hidden="true"]')).toBeTruthy();
  });

  it("animates to a value that arrives after mount (async stats)", async () => {
    cleanup();
    // Stats pages render the counter with 0 before the fetch resolves.
    const { rerender } = render(StatCounter, { props: { value: 0, duration: 10 } });
    const digits = () =>
      screen.getByLabelText("1.234").querySelector('[aria-hidden="true"]')?.textContent ?? "";
    await rerender({ value: 1234, duration: 10 });
    // The counter must pick up the late value rather than staying latched at 0.
    // The mocked IntersectionObserver never fires, so the mount safety-net
    // (1500ms) is what starts the animation — wait past it.
    await waitFor(() => expect(digits().replace(/\./g, "")).toBe("1234"), { timeout: 4000 });
  });
});
