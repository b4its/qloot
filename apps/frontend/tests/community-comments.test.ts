// @vitest-environment jsdom
import { describe, it, expect } from "vitest";
import communitySrc from "$routes-site/community/+page.svelte?raw";

describe("community comment editing and nested replies (COMM-02)", () => {
  it("supports replying to a comment (parent_id)", () => {
    expect(communitySrc).toContain("replyTo");
    expect(communitySrc).toContain("parent_id");
  });

  it("supports editing a comment via PATCH", () => {
    expect(communitySrc).toContain("api.patch(`/community/comments/");
    expect(communitySrc).toContain("editComment");
  });

  it("shows an edited marker", () => {
    expect(communitySrc).toContain("disunting");
    expect(communitySrc).toContain("edited_at");
  });
});
