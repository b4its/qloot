// @vitest-environment jsdom
import { describe, it, expect } from "vitest";
import { adminNav } from "$lib/data/role-nav";
import communitySrc from "$routes-site/community/+page.svelte?raw";
import moderationSrc from "$routes-panel/admin/moderation/+page.svelte?raw";

describe("community reporting and moderation (COMM-01)", () => {
  it("users can report posts and comments", () => {
    expect(communitySrc).toContain("/community/reports");
    expect(communitySrc).toContain('reportTarget("post"');
    expect(communitySrc).toContain('reportTarget("comment"');
  });

  it("admin moderation queue is linked from the nav", () => {
    expect(adminNav.some((n) => n.href === "/admin/moderation")).toBe(true);
  });

  it("moderation page calls the queue and moderate endpoints", () => {
    expect(moderationSrc).toContain("/community/reports");
    expect(moderationSrc).toContain("/moderate");
    expect(moderationSrc).toContain("Sembunyikan");
  });
});
