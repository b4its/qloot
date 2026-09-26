// @vitest-environment jsdom
import { describe, it, expect } from "vitest";
import adminNotificationsSrc from "$routes-panel/admin/notifications/+page.svelte?raw";
import { adminNav } from "$lib/data/role-nav";

describe("admin broadcast notifications panel", () => {
  it("role-nav contains the notifications broadcast link", () => {
    const item = adminNav.find((n) => n.href === "/admin/notifications");
    expect(item).toBeDefined();
    expect(item?.label).toContain("Notifikasi");
  });

  it("page posts to /admin/notifications with title, body, and kind", () => {
    expect(adminNotificationsSrc).toContain("api.post");
    expect(adminNotificationsSrc).toContain("/admin/notifications");
    expect(adminNotificationsSrc).toContain("title");
    expect(adminNotificationsSrc).toContain("kind");
    expect(adminNotificationsSrc).toContain("body");
  });
});
