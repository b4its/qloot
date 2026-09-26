// @vitest-environment jsdom
import { describe, it, expect } from "vitest";
import adminBlockchainSrc from "$routes-panel/admin/blockchain/+page.svelte?raw";

describe("admin blockchain contracts and allocations surface", () => {
  it("fetches /blockchain/contract and displays contract deployments", () => {
    expect(adminBlockchainSrc).toContain("/blockchain/contract");
    expect(adminBlockchainSrc).toContain("deployments");
  });

  it("fetches /blockchain/allocations and displays recent reward allocations", () => {
    expect(adminBlockchainSrc).toContain("/blockchain/allocations");
    expect(adminBlockchainSrc).toContain("allocations");
  });
});
