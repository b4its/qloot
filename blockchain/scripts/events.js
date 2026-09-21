// Dump recent contract events.
//
// Discovers event names from the attached contract's ABI so it never drifts
// from the deployed contract (legacy hard-coded names used to crash here).
const { ethers } = require("hardhat");
const lib = require("./_lib");

async function main() {
  const dep = lib.readDeployment();
  const opc = await lib.attach(dep.address);
  const current = await ethers.provider.getBlockNumber();
  const fromBlock = Math.max(0, current - Number(process.env.LOOKBACK_BLOCKS || 5000));

  console.log(`Contract : ${dep.address} (${dep.contractName || "OryphemCoin"})`);
  console.log(`Scanning events from block ${fromBlock} to ${current} ...`);

  // Derive event names from the ABI fragments (ethers v6 `Contract.filters`
  // keys are not enumerable, and `interface.events` only exists on some shims).
  const names = opc.interface.fragments.filter((f) => f.type === "event").map((f) => f.name);
  const unique = [...new Set(names)];

  let found = 0;
  for (const name of unique) {
    const events = await opc.queryFilter(opc.filters[name](), fromBlock, current);
    for (const ev of events) {
      const args = (ev.args || []).map((v) => (typeof v === "bigint" ? v.toString() : v));
      console.log(`[${ev.blockNumber}] ${name} ${JSON.stringify(args)}`);
      found += 1;
    }
  }
  console.log(`\n${found} event(s) found.`);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
