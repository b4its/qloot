// @vitest-environment jsdom
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { connectWalletAddress, hasInjectedWallet } from "../src/lib/utils/metamask";

describe("metamask util", () => {
  beforeEach(() => {
    delete (window as unknown as { ethereum?: unknown }).ethereum;
  });
  afterEach(() => {
    delete (window as unknown as { ethereum?: unknown }).ethereum;
  });

  it("reports no injected wallet when window.ethereum is missing", () => {
    expect(hasInjectedWallet()).toBe(false);
  });

  it("detects an injected wallet", () => {
    (window as unknown as { ethereum: unknown }).ethereum = { request: vi.fn() };
    expect(hasInjectedWallet()).toBe(true);
  });

  it("throws a friendly error when no provider is present", async () => {
    await expect(connectWalletAddress()).rejects.toThrow(/MetaMask tidak terdeteksi/);
  });

  it("returns the first account from eth_requestAccounts", async () => {
    const request = vi.fn().mockResolvedValue(["0xAbC0000000000000000000000000000000000001"]);
    (window as unknown as { ethereum: unknown }).ethereum = { request };
    const addr = await connectWalletAddress();
    expect(addr).toBe("0xAbC0000000000000000000000000000000000001");
    expect(request).toHaveBeenCalledWith({ method: "eth_requestAccounts" });
  });

  it("maps a user rejection (code 4001) to a friendly error", async () => {
    const request = vi.fn().mockRejectedValue({ code: 4001 });
    (window as unknown as { ethereum: unknown }).ethereum = { request };
    await expect(connectWalletAddress()).rejects.toThrow(/dibatalkan/);
  });

  it("throws when no account is returned", async () => {
    const request = vi.fn().mockResolvedValue([]);
    (window as unknown as { ethereum: unknown }).ethereum = { request };
    await expect(connectWalletAddress()).rejects.toThrow(/Tidak ada akun/);
  });
});
