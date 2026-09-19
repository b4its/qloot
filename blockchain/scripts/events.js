// Dump recent contract events.
const { ethers } = require("hardhat");
const lib = require("./_lib");

async function main() {
  const dep = lib.readDeployment();
  const opc = await lib.attach(dep.address);
  const current = await ethers.provider.getBlockNumber();
  const fromBlock = Math.max(0, current - Number(process.env.LOOKBACK_BLOCKS || 5000));

  console.log(`Scanning events from block ${fromBlock} to ${current} ...`);

  const names = [
    "RewardGranted",
    "QuestRewardFinalized",
    "CustodialAllocation",
    "CustodialTransfer",
    "WithdrawalRequested",
    "WithdrawalCompleted",
    "MetadataPublished",
    "LimitsUpdated",
    "TransferSingle",
  ];

  for (const name of names) {
    const filter = opc.filters[name]();
    const events = await opc.queryFilter(filter, fromBlock, current);
    for (const ev of events) {
      const args = ev.args.map((v) => (typeof v === "bigint" ? v.toString() : v));
      console.log(`[${ev.blockNumber}] ${name} ${JSON.stringify(args)}`);
    }
  }
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
