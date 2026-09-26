// @vitest-environment jsdom
import { describe, it, expect } from "vitest";
import walletSrc from "$routes-site/wallet/+page.svelte?raw";

describe("wallet UI quick actions & presets", () => {
  it("provides quick percentage buttons for withdrawal amount", () => {
    expect(walletSrc).toContain("setWithdrawPercent(25)");
    expect(walletSrc).toContain("setWithdrawPercent(50)");
    expect(walletSrc).toContain("setWithdrawPercent(100)");
  });

  it("provides quick percentage buttons for transfer amount", () => {
    expect(walletSrc).toContain("setTransferPercent(25)");
    expect(walletSrc).toContain("setTransferPercent(50)");
    expect(walletSrc).toContain("setTransferPercent(100)");
  });

  it("provides preset amount buttons and max calculation for ORX swaps", () => {
    expect(walletSrc).toContain("setSwapAmount(1)");
    expect(walletSrc).toContain("setSwapAmount(10)");
    expect(walletSrc).toContain("setMaxSwap");
  });

  it("includes click-to-copy address button with feedback indicator", () => {
    expect(walletSrc).toContain("copyToClipboard");
    expect(walletSrc).toContain("copiedAddr");
    expect(walletSrc).toContain("Tersalin!");
  });
});
