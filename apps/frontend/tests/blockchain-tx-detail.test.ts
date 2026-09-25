// @vitest-environment jsdom
import { describe, it, expect } from "vitest";
import txSrc from "$routes-panel/admin/blockchain/transactions/+page.svelte?raw";

/**
 * The admin transaction list must surface the tx-detail endpoint (gas metrics,
 * arguments hash, events) so those DB columns have a real reader in the UI.
 */
describe("admin blockchain tx detail (gas inline)", () => {
  it("calls GET /blockchain/transactions/{hash} from a row action", () => {
    expect(txSrc).toContain("/blockchain/transactions/${tx.transaction_hash}");
    expect(txSrc).toContain("openDetail");
  });

  it("renders gas_limit / gas_used / effective_gas_price / arguments_hash", () => {
    expect(txSrc).toContain("detail.gas_limit");
    expect(txSrc).toContain("detail.gas_used");
    expect(txSrc).toContain("detail.effective_gas_price");
    expect(txSrc).toContain("detail.arguments_hash");
  });
});
