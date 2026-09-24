// @vitest-environment jsdom
import { describe, it, expect } from "vitest";
import notificationsSrc from "$routes-site/notifications/+page.svelte?raw";

describe("community notification preference (COMM-03)", () => {
  it("exposes a mappable 'community' notification kind", () => {
    expect(notificationsSrc).toContain("community:");
    expect(notificationsSrc).toContain("Komunitas");
  });
});
