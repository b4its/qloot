// @vitest-environment jsdom
import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import tailwindConfig from "../tailwind.config.ts?raw";
import progressRing from "$lib/components/ProgressRing.svelte?raw";

const appCss = readFileSync("src/app.css", "utf8");

describe("blue-first cyberpunk design contract", () => {
  it("uses electric blue as the semantic primary color", () => {
    expect(tailwindConfig).toMatch(/primary:\s*\{[\s\S]*?DEFAULT:\s*"#168BFF"/);
    expect(appCss).toContain("--neon-blue: 22 139 255");
    expect(appCss).toContain("--accent: 22 139 255");
  });

  it("keeps yellow as an explicit reward color instead of the primary action", () => {
    expect(tailwindConfig).toContain('reward: { DEFAULT: "#FCEE0A"');
    expect(appCss).toContain("--neon-yellow: 252 238 10");
    const primaryBlock = tailwindConfig.slice(
      tailwindConfig.indexOf("primary: {"),
      tailwindConfig.indexOf("// `secondary`"),
    );
    expect(primaryBlock).not.toContain("#FCEE0A");
  });

  it("renders shared progress with blue-to-cyan semantic tokens", () => {
    expect(progressRing).toContain('stop-color="rgb(var(--neon-blue))"');
    expect(progressRing).toContain('stop-color="rgb(var(--neon-cyan))"');
  });

  it("uses blue primary buttons while preserving reduced-motion support", () => {
    expect(appCss).toMatch(/\.btn-primary\s*\{[\s\S]*?var\(--neon-blue\)/);
    expect(appCss).toContain("@media (prefers-reduced-motion: reduce)");
  });
});
