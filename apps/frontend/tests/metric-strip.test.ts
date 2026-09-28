// @vitest-environment jsdom
import { describe, it, expect } from "vitest";
import { render, screen, cleanup } from "@testing-library/svelte";
import MetricStrip from "$lib/components/MetricStrip.svelte";

describe("MetricStrip", () => {
  it("renders each metric label and value", () => {
    render(MetricStrip, {
      props: {
        metrics: [
          { label: "Pelajaran", value: 12 },
          { label: "Berjalan", value: 3, tone: "text-highlight" },
          { label: "Selesai", value: 5, role: "done-courses" },
        ],
      },
    });
    expect(screen.getByText("Pelajaran")).toBeTruthy();
    expect(screen.getByText("12")).toBeTruthy();
    expect(screen.getByText("Berjalan")).toBeTruthy();
    expect(screen.getByText("3")).toBeTruthy();
    cleanup();
  });

  it("forwards data-role to the value element", () => {
    render(MetricStrip, {
      props: { metrics: [{ label: "Selesai", value: 5, role: "done-courses" }] },
    });
    expect(document.querySelector('[data-role="done-courses"]')?.textContent?.trim()).toBe("5");
    cleanup();
  });

  it("renders nothing when there are no metrics", () => {
    const { container } = render(MetricStrip, { props: { metrics: [] } });
    expect(container.querySelector(".card")).toBeNull();
    cleanup();
  });
});
