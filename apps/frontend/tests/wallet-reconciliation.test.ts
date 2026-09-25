// @vitest-environment jsdom
import { describe, it, expect } from "vitest";
import walletSrc from "$routes-site/wallet/+page.svelte?raw";

describe("wallet reconciliation check (UI reader)", () => {
  it("calls GET /wallet/reconciliation from a verify control", () => {
    expect(walletSrc).toContain('"/wallet/reconciliation"');
    expect(walletSrc).toContain("checkReconciliation");
    expect(walletSrc).toContain("Verifikasi saldo");
  });

  it("renders the ok / mismatch result", () => {
    expect(walletSrc).toContain("recon.ok");
    expect(walletSrc).toContain("recon.computed_balance");
  });
});
