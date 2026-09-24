// @vitest-environment jsdom
import { describe, it, expect } from "vitest";
import { adminNav } from "$lib/data/role-nav";
// Raw source of the admin config page — asserts the surface exists without
// mounting the full page (which needs the auth store + navigation).
import configSrc from "$routes-panel/admin/config/+page.svelte?raw";
import usersSrc from "$routes-panel/admin/users/+page.svelte?raw";

describe("admin config panel (AUTH-11)", () => {
  it("is linked from the admin nav", () => {
    expect(adminNav.some((n) => n.href === "/admin/config")).toBe(true);
  });

  it("consumes the /admin/config endpoint", () => {
    expect(configSrc).toContain("/admin/config");
  });

  it("never renders secret-bearing config keys", () => {
    for (const forbidden of ["rpc_url", "private_key", "session_secret", "minio_secret"]) {
      expect(configSrc.toLowerCase()).not.toContain(forbidden);
    }
  });
});

describe("admin users pagination totals (AUTH-11)", () => {
  it("reads the total from the paged API helper", () => {
    expect(usersSrc).toContain("apiGetPaged");
    expect(usersSrc).toContain("total");
  });
});
