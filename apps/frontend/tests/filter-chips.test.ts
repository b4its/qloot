// @vitest-environment jsdom
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/svelte";
import FilterChips from "$lib/components/FilterChips.svelte";

const options: readonly (readonly [string, string])[] = [
  ["all", "Semua"],
  ["new", "Baru"],
  ["done", "Selesai"],
];

describe("FilterChips", () => {
  it("renders each option and marks the selected one as pressed", () => {
    render(FilterChips, { props: { options, value: "new", label: "Status" } });
    const group = screen.getByRole("group", { name: "Status" });
    expect(group).toBeTruthy();
    expect(screen.getByRole("button", { name: "Baru" }).getAttribute("aria-pressed")).toBe("true");
    expect(screen.getByRole("button", { name: "Semua" }).getAttribute("aria-pressed")).toBe(
      "false",
    );
    cleanup();
  });

  it("fires onchange with the next value when a different chip is clicked", async () => {
    const onchange = vi.fn();
    render(FilterChips, { props: { options, value: "all", label: "Status", onchange } });
    await fireEvent.click(screen.getByRole("button", { name: "Selesai" }));
    expect(onchange).toHaveBeenCalledWith("done");
    cleanup();
  });

  it("does not fire onchange when the active chip is re-clicked", async () => {
    const onchange = vi.fn();
    render(FilterChips, { props: { options, value: "all", label: "Status", onchange } });
    await fireEvent.click(screen.getByRole("button", { name: "Semua" }));
    expect(onchange).not.toHaveBeenCalled();
    cleanup();
  });

  it("uses ariaLabel to override the accessible group name", () => {
    render(FilterChips, {
      props: { options, value: "all", label: "ignored", ariaLabel: "Filter status badge" },
    });
    expect(screen.getByRole("group", { name: "Filter status badge" })).toBeTruthy();
    cleanup();
  });
});
