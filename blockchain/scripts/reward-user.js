// Pay an idempotent OPC reward.
//   TO=0x.. AMOUNT=100 REASON=quest KEY=1 make blockchain-reward
const { ethers } = require("hardhat");
const lib = require("./_lib");

async function main() {
  const to = process.env.TO;
  const amount = process.env.AMOUNT;
  const reason = lib.toBytes32(process.env.REASON || "reward");
  const key = process.env.KEY;
  if (!to || !ethers.isAddress(to)) throw new Error("TO (address) is required");
  if (!amount || BigInt(amount) <= 0n) throw new Error("AMOUNT (>0) is required");
  if (!key) throw new Error("KEY (idempotency uint) is required");
  const opc = await lib.getDeployedContract();
  const tx = await opc.rewardUser(to, BigInt(amount), reason, BigInt(key));
  console.log(`rewardUser tx: ${tx.hash}`);
  await tx.wait();
  console.log(`rewarded ${amount} OPC to ${to}; balance=${await opc.balanceOf(to, 0)}`);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
