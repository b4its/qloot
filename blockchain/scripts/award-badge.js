// Award a badge to an address.
//   TO=0x.. BADGE_ID=1 make blockchain-award-badge
const { ethers } = require("hardhat");
const lib = require("./_lib");

async function main() {
  const to = process.env.TO;
  const badgeId = Number(process.env.BADGE_ID || "0");
  if (!to || !ethers.isAddress(to)) throw new Error("TO (address) is required");
  if (!badgeId) throw new Error("BADGE_ID is required");
  const opc = await lib.getDeployedContract();
  const tx = await opc.awardBadge(to, badgeId, "");
  console.log(`awardBadge tx: ${tx.hash}`);
  await tx.wait();
  console.log(`badge ${badgeId} awarded to ${to}.`);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
