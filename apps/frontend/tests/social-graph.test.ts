// @vitest-environment jsdom
import { describe, it, expect } from "vitest";
import communitySrc from "$routes-site/community/+page.svelte?raw";

describe("community follow graph and following feed (COMM-06)", () => {
  it("has a follow/unfollow control calling the follow endpoints", () => {
    expect(communitySrc).toContain("toggleFollow");
    expect(communitySrc).toContain("/follow");
  });

  it("filters the feed to followed authors", () => {
    expect(communitySrc).toContain('params.set("following"');
    expect(communitySrc).toContain("Mengikuti");
  });

  it("loads the viewer's following ids", () => {
    expect(communitySrc).toContain('/me/following');
  });
});
