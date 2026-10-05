// @vitest-environment jsdom
import { afterEach, describe, expect, it } from "vitest";
import { render, screen, cleanup } from "@testing-library/svelte";
import Mascot from "../src/lib/components/Mascot.svelte";

describe("Mascot component", () => {
  afterEach(() => cleanup());

  it("renders default expression (cool) with alt text", () => {
    const { container } = render(Mascot);
    const img = container.querySelector("img");
    expect(img).toBeTruthy();
    expect(img?.getAttribute("src")).toBe("/mascot/expressions/cool.webp");
    expect(img?.getAttribute("alt")).toBe("Mascot Qlo");
  });

  it("renders custom expressions correctly", () => {
    const { container } = render(Mascot, { props: { expression: "thinking" } });
    const img = container.querySelector("img");
    expect(img?.getAttribute("src")).toBe("/mascot/expressions/thinking.webp");
  });

  it("renders full body pose when mode is 'pose'", () => {
    const { container } = render(Mascot, { props: { mode: "pose", pose: "front" } });
    const img = container.querySelector("img");
    expect(img?.getAttribute("src")).toBe("/mascot/poses/front.webp");
  });

  it("renders speech bubble when speech text is passed", () => {
    render(Mascot, { props: { speech: "Semangat belajarnya!" } });
    const bubble = screen.getByRole("tooltip");
    expect(bubble).toBeTruthy();
    expect(bubble.textContent).toContain("Semangat belajarnya!");
  });

  it("applies animation and glow classes when requested", () => {
    const { container } = render(Mascot, { props: { float: true, glow: true } });
    const root = container.firstElementChild;
    expect(root?.classList.contains("animate-float")).toBe(true);

    const aura = container.querySelector(".blur-xl");
    expect(aura).toBeTruthy();
  });

  it("renders cat mascot Qlu with proper alt and front pose by default", () => {
    const { container } = render(Mascot, { props: { character: "qlu" } });
    const img = container.querySelector("img");
    expect(img).toBeTruthy();
    expect(img?.getAttribute("src")).toBe("/mascot/qlu/front.webp");
    expect(img?.getAttribute("alt")).toBe("Mascot Qlu");
  });

  it("renders cat mascot Qlu side pose for thinking expression", () => {
    const { container } = render(Mascot, { props: { character: "qlu", expression: "thinking" } });
    const img = container.querySelector("img");
    expect(img?.getAttribute("src")).toBe("/mascot/qlu/side.webp");
  });

  it("renders specific poses for Qlu when mode is 'pose'", () => {
    const { container } = render(Mascot, {
      props: { character: "qlu", mode: "pose", pose: "side" },
    });
    const img = container.querySelector("img");
    expect(img?.getAttribute("src")).toBe("/mascot/qlu/side.webp");
  });
});
