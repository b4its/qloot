// Pay an idempotent reward (any asset).
//   ASSET=OPT TO=0x.. AMOUNT=100 REASON=quest KEY=1 make blockchain-reward
const { ethers } = require("hardhat");
const lib = require("./_lib");

async function main() {
  const key = (process.env.ASSET || "OPT").toUpperCase();
  const to = process.env.TO;
  const amount = process.env.AMOUNT;
  const reason = lib.toBytes32(process.env.REASON || "reward");
  const rewardKey = process.env.KEY;

  if (!lib.CONTRACTS[key] || key === "ORX") {
    throw new Error("ASSET must be one of OPT, QTC, ORT");
  }
  if (!to || !ethers.isAddress(to)) throw new Error("TO (address) is required");
  if (!amount || BigInt(amount) <= 0n) throw new Error("AMOUNT (>0) is required");
  if (!rewardKey) throw new Error("KEY (idempotency uint) is required");

  const token = await lib.attach(key);
  const tx = await token.rewardUser(to, BigInt(amount), reason, BigInt(rewardKey));
  console.log(`${key} rewardUser tx: ${tx.hash}`);
  await tx.wait();
  console.log(`rewarded ${amount} ${key} to ${to}; balance=${await token.balanceOf(to, 0)}`);
}

main().catch((e) => {
  console.error(e.message || e);
  process.exit(1);
});
