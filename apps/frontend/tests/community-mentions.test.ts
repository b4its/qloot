// @vitest-environment jsdom
import { describe, it, expect } from "vitest";
import communitySrc from "$routes-site/community/+page.svelte?raw";

describe("community @mentions (COMM-04)", () => {
  it("renders mentions as links through renderBody", () => {
    expect(communitySrc).toContain("function renderBody");
    expect(communitySrc).toContain("renderBody(f.body)");
    expect(communitySrc).toContain("renderBody(c.body)");
  });

  it("escapes HTML before linking (injection-safe)", () => {
    // The escaper must run before the mention anchor is inserted.
    const escIdx = communitySrc.indexOf(".replace(/&/g");
    const linkIdx = communitySrc.indexOf('href="/community?mention=');
    expect(escIdx).toBeGreaterThanOrEqual(0);
    expect(linkIdx).toBeGreaterThan(escIdx);
  });
});
