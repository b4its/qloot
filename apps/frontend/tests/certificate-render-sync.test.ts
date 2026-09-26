// @vitest-environment jsdom
import { describe, it, expect } from "vitest";
import certPageSrc from "$routes-site/certificates/+page.svelte?raw";
import verifyPageSrc from "$routes-site/verify/[credentialId]/+page.svelte?raw";

describe("certificates sync and official document rendering", () => {
  it("certificates page provides manual sync via POST /certificates/sync", () => {
    expect(certPageSrc).toContain("/certificates/sync");
    expect(certPageSrc).toContain("syncCertificates");
  });

  it("certificates page opens server-rendered certificate (/render)", () => {
    expect(certPageSrc).toContain("/certificates/${active.credential_id}/render");
  });

  it("verify page links to server-rendered certificate document (/render)", () => {
    expect(verifyPageSrc).toContain("/certificates/${credentialId}/render");
  });
});
