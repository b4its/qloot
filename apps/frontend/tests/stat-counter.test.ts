// @vitest-environment jsdom
import { describe, it, expect, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/svelte";

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
});
