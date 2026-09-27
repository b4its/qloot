// @vitest-environment jsdom
import { describe, it, expect, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/svelte";

import AddressAvatar from "$lib/components/AddressAvatar.svelte";

describe("AddressAvatar", () => {
  afterEach(() => cleanup());

  it("is decorative by default (no duplicate announcement in labelled parents)", () => {
    cleanup();
    const { container } = render(AddressAvatar, { props: { seed: "0xabc" } });
    const el = container.querySelector(".addr-avatar")!;
    expect(el.getAttribute("aria-hidden")).toBe("true");
    expect(el.getAttribute("role")).toBeNull();
  });

  it("exposes role=img when given a label", () => {
    cleanup();
    const { container } = render(AddressAvatar, { props: { seed: "0xabc", label: "Avatar X" } });
    const el = container.querySelector(".addr-avatar")!;
    expect(el.getAttribute("role")).toBe("img");
    expect(el.getAttribute("aria-label")).toBe("Avatar X");
  });
});
