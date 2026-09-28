// @vitest-environment jsdom
import { describe, it, expect } from "vitest";
import tailwindConfig from "../tailwind.config.ts?raw";
import progressRing from "$lib/components/ProgressRing.svelte?raw";

describe("blue-first cyberpunk design contract", () => {
  it("uses electric blue as the semantic primary color", () => {
    expect(tailwindConfig).toMatch(/primary:\s*\{[\s\S]*?DEFAULT:\s*"#168BFF"/);
    expect(tailwindConfig).toContain('"grad-signature": "linear-gradient(135deg, #168BFF');
  });

  it("keeps yellow as an explicit reward color instead of the primary action", () => {
    expect(tailwindConfig).toContain('reward: { DEFAULT: "#FCEE0A"');
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
    expect(tailwindConfig).toContain('glow: "0 0 26px -4px rgba(22,139,255,.65)"');
    expect(tailwindConfig).toContain('"pulse-neon": "pulseNeon 2.6s ease-in-out infinite"');
  });
});
