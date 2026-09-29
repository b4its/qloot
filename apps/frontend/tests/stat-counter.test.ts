// @vitest-environment jsdom
import { describe, it, expect, afterEach, beforeEach, vi } from "vitest";
import { render, screen, cleanup, waitFor } from "@testing-library/svelte";

import StatCounter from "$lib/components/StatCounter.svelte";

describe("StatCounter semantics", () => {
  beforeEach(() => {
    // The default mock never fires, which would leave the counter waiting for
    // the 1500ms mount fallback. Fire synchronously so "started" is immediate
    // and the test exercises the re-animation, not a timer.
    class ImmediateIO {
      observe(el: Element) {
        this.cb(
          [{ isIntersecting: true, target: el } as IntersectionObserverEntry],
          this as unknown as IntersectionObserver,
        );
      }
      unobserve() {}
      disconnect() {}
      takeRecords() {
        return [];
      }
      root = null;
      rootMargin = "";
      thresholds = [];
      constructor(private cb: IntersectionObserverCallback) {}
    }
    vi.stubGlobal("IntersectionObserver", ImmediateIO as unknown as typeof IntersectionObserver);
  });
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

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
    await waitFor(() => expect(digits().replace(/\./g, "")).toBe("1234"));
  });
});
