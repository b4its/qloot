// @vitest-environment jsdom
import { describe, it, expect } from "vitest";
import communitySrc from "$routes-site/community/+page.svelte?raw";

describe("public user level card surface", () => {
  it("community page allows inspecting a user level card via /gamification/levels/{id}", () => {
    expect(communitySrc).toContain("/gamification/levels/");
    expect(communitySrc).toContain("inspectUserLevel");
    expect(communitySrc).toContain("inspectingLevel");
  });
});
