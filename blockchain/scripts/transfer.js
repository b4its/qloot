// Transfer a QLoot asset.
//   ASSET=OPT TO=0x.. AMOUNT=250 make blockchain-transfer
const { ethers } = require("hardhat");
const lib = require("./_lib");

async function main() {
  const key = (process.env.ASSET || "OPT").toUpperCase();
  const to = process.env.TO;
  const amount = process.env.AMOUNT;

  if (!lib.CONTRACTS[key] || key === "ORX") {
    throw new Error("ASSET must be one of OPT, QTC, ORT");
  }
  if (!to || !ethers.isAddress(to)) throw new Error("TO (address) is required");
  if (!amount || BigInt(amount) <= 0n) throw new Error("AMOUNT (>0) is required");

  const token = await lib.attach(key);
  const from = process.env.FROM || (await ethers.getSigners())[0].address;
  const tx = await token.safeTransferFrom(from, to, 0, BigInt(amount), "0x");
  console.log(`${key} transfer tx: ${tx.hash}`);
  await tx.wait();
  console.log(`new balance ${to} = ${await token.balanceOf(to, 0)}`);
}

main().catch((e) => {
  console.error(e.message || e);
  process.exit(1);
});
