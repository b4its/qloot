// @vitest-environment jsdom
import { afterEach, describe, expect, it } from "vitest";
import { render, screen, cleanup } from "@testing-library/svelte";
import BrandLogo from "../src/lib/components/BrandLogo.svelte";

describe("BrandLogo component", () => {
  afterEach(() => cleanup());

  it("renders horizontal full logo by default with both light and dark pictures", () => {
    const { container } = render(BrandLogo);
    const imgLight = container.querySelector("img[src*='logo-light']");
    const imgDark = container.querySelector("img[src*='logo-dark']");

    expect(imgLight).toBeTruthy();
    expect(imgDark).toBeTruthy();
    expect(screen.getByRole("img", { name: "QLoot" })).toBeTruthy();
  });

  it("renders symbol mark when variant is 'symbol'", () => {
    const { container } = render(BrandLogo, { props: { variant: "symbol" } });
    const imgLight = container.querySelector("img[src*='symbol-light']");
    const imgDark = container.querySelector("img[src*='symbol-dark']");

    expect(imgLight).toBeTruthy();
    expect(imgDark).toBeTruthy();
  });

  it("renders app icon when variant is 'icon'", () => {
    const { container } = render(BrandLogo, { props: { variant: "icon" } });
    const imgLight = container.querySelector("img[src*='icon-light']");
    const imgDark = container.querySelector("img[src*='icon-dark']");

    expect(imgLight).toBeTruthy();
    expect(imgDark).toBeTruthy();
  });

  it("renders as anchor link when asLink is true", () => {
    render(BrandLogo, { props: { asLink: true, href: "/custom" } });
    const link = screen.getByRole("link", { name: "QLoot" });
    expect(link.getAttribute("href")).toBe("/custom");
  });
});
