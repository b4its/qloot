// @vitest-environment jsdom
import { describe, it, expect } from "vitest";
import communitySrc from "$routes-site/community/+page.svelte?raw";

describe("community hot/top feed ranking (COMM-05)", () => {
  it("sends the sort parameter", () => {
    expect(communitySrc).toContain('params.set("sort"');
  });

  it("exposes Terbaru / Populer / Teratas controls", () => {
    expect(communitySrc).toContain("Terbaru");
    expect(communitySrc).toContain("Populer");
    expect(communitySrc).toContain("Teratas");
  });
});
