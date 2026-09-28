// @vitest-environment jsdom
import { describe, it, expect } from "vitest";
import walletSrc from "$routes-site/wallet/+page.svelte?raw";

describe("wallet settlement explanation (W4)", () => {
  it("explains the withdrawal lifecycle from request to confirmation", () => {
    expect(walletSrc).toContain('data-role="settlement-guide"');
    expect(walletSrc).toMatch(/Diminta/);
    expect(walletSrc).toMatch(/Disetujui/);
    expect(walletSrc).toMatch(/Dikirim/);
    expect(walletSrc).toMatch(/Terkonfirmasi/);
  });

  it("distinguishes reward states including failure compensation", () => {
    expect(walletSrc).toMatch(/Menunggu/);
    expect(walletSrc).toMatch(/Gagal/);
    expect(walletSrc).toMatch(/dikembalikan otomatis/);
  });

  it("clarifies that balance verification is ledger integrity, not chain confirmation", () => {
    expect(walletSrc).toMatch(/integritas buku besar/i);
    expect(walletSrc).toMatch(/bukan konfirmasi/i);
  });
});
