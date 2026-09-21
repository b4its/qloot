// Dump recent events for a QLoot contract (default ASSET=OPT).
//   ASSET=ORX make blockchain-events
// Names are discovered from the attached contract's ABI so it never drifts.
const { ethers } = require("hardhat");
const lib = require("./_lib");

async function main() {
  const key = (process.env.ASSET || "OPT").toUpperCase();
  if (!lib.CONTRACTS[key])
    throw new Error(`ASSET must be one of ${Object.keys(lib.CONTRACTS).join(", ")}`);

  const dep = lib.readDeployment();
  const token = await lib.attach(key, dep);
  const current = await ethers.provider.getBlockNumber();
  const fromBlock = Math.max(0, current - Number(process.env.LOOKBACK_BLOCKS || 5000));

  console.log(`Contract : ${await token.getAddress()} (${key})`);
  console.log(`Scanning events from block ${fromBlock} to ${current} ...`);

  const names = token.interface.fragments.filter((f) => f.type === "event").map((f) => f.name);
  const unique = [...new Set(names)];

  let found = 0;
  for (const name of unique) {
    const events = await token.queryFilter(token.filters[name](), fromBlock, current);
    for (const ev of events) {
      const args = (ev.args || []).map((v) => (typeof v === "bigint" ? v.toString() : v));
      console.log(`[${ev.blockNumber}] ${name} ${JSON.stringify(args)}`);
      found += 1;
    }
  }
  console.log(`\n${found} event(s) found.`);
}

main().catch((e) => {
  console.error(e.message || e);
  process.exit(1);
});
