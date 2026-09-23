// @vitest-environment jsdom
import { describe, it, expect } from "vitest";
import { adminNav } from "$lib/data/role-nav";
// Raw source of the admin review page — asserts the controls exist without
// mounting the full page (which needs auth store + navigation).
import withdrawalsSrc from "$routes-panel/admin/withdrawals/+page.svelte?raw";
import walletSrc from "$routes-site/wallet/+page.svelte?raw";

describe("admin withdrawals review panel", () => {
  it("is linked from the admin nav", () => {
    expect(adminNav.some((n) => n.href === "/admin/withdrawals")).toBe(true);
  });

  it("calls the approve and reject endpoints", () => {
    expect(withdrawalsSrc).toContain("/admin/withdrawals/");
    expect(withdrawalsSrc).toContain("/approve");
    expect(withdrawalsSrc).toContain("/reject");
  });
});

describe("user-side withdrawal cancel", () => {
  it("calls the cancel endpoint from the wallet page", () => {
    expect(walletSrc).toContain("/cancel");
    expect(walletSrc).toContain("loadWithdrawals");
  });
});
