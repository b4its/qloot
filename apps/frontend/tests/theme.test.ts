// @vitest-environment jsdom
import { describe, it, expect, beforeEach } from "vitest";
import { get } from "svelte/store";
import { theme } from "../src/lib/stores/theme";

describe("theme store", () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.classList.remove("dark");
  });

  it("defaults to light when system prefers light", () => {
    theme.init();
    expect(get(theme)).toBe("light");
    expect(document.documentElement.classList.contains("dark")).toBe(false);
  });

  it("toggles to dark and persists", () => {
    theme.set("light");
    theme.toggle();
    expect(get(theme)).toBe("dark");
    expect(document.documentElement.classList.contains("dark")).toBe(true);
    expect(localStorage.getItem("qloot-theme")).toBe("dark");
  });

  it("respects a persisted preference", () => {
    localStorage.setItem("qloot-theme", "dark");
    theme.init();
    expect(get(theme)).toBe("dark");
    expect(document.documentElement.classList.contains("dark")).toBe(true);
  });
});
