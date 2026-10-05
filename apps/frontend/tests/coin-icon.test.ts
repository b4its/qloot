// @vitest-environment jsdom
import { afterEach, describe, expect, it } from "vitest";
import { render, screen, cleanup } from "@testing-library/svelte";
import CoinIcon from "../src/lib/components/CoinIcon.svelte";
import Icon from "../src/lib/components/Icon.svelte";

describe("CoinIcon component", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders an img element with /coin/coinIcon.webp src", () => {
    render(CoinIcon, { props: { size: "24px", alt: "Koin QLoot" } });
    const img = screen.getByRole("img", { name: "Koin QLoot" }) as HTMLImageElement;
    expect(img).toBeTruthy();
    expect(img.getAttribute("src")).toBe("/coin/coinIcon.webp");
    expect(img.style.width).toBe("24px");
    expect(img.style.height).toBe("24px");
  });

  it("applies default size and alt text when not specified", () => {
    render(CoinIcon);
    const img = screen.getByRole("img", { name: "Koin" }) as HTMLImageElement;
    expect(img).toBeTruthy();
    expect(img.getAttribute("src")).toBe("/coin/coinIcon.webp");
    expect(img.style.width).toBe("1em");
    expect(img.style.height).toBe("1em");
  });

  it("delegates name='coins' in Icon.svelte to CoinIcon", () => {
    render(Icon, { props: { name: "coins", size: "18px", label: "Mata Uang OPT" } });
    const img = screen.getByRole("img", { name: "Mata Uang OPT" }) as HTMLImageElement;
    expect(img).toBeTruthy();
    expect(img.getAttribute("src")).toBe("/coin/coinIcon.webp");
    expect(img.style.width).toBe("18px");
    expect(img.style.height).toBe("18px");
  });
});
