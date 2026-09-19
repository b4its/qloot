// Grant XP to an address (raises level).
//   TO=0x.. AMOUNT=250 make blockchain-add-xp
const { ethers } = require("hardhat");
const lib = require("./_lib");

async function main() {
  const to = process.env.TO;
  const amount = process.env.AMOUNT;
  if (!to || !ethers.isAddress(to)) throw new Error("TO (address) is required");
  if (!amount || BigInt(amount) <= 0n) throw new Error("AMOUNT (>0) is required");
  const opc = await lib.getDeployedContract();
  const tx = await opc.addXp(to, BigInt(amount));
  console.log(`addXp tx: ${tx.hash}`);
  await tx.wait();
  console.log(`${to}: xp=${await opc.xp(to)} level=${await opc.level(to)}`);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
