// Mint a QLoot asset into a recipient.
//   ASSET=OPT TO=0x.. AMOUNT=1000 make blockchain-mint
//   ASSET=QTC|ORT ... (default ASSET=OPT)
const { ethers } = require("hardhat");
const lib = require("./_lib");

async function main() {
  const key = (process.env.ASSET || "OPT").toUpperCase();
  const to = process.env.TO || process.env.TREASURY_ADDRESS;
  const amount = process.env.AMOUNT;

  if (!lib.CONTRACTS[key] || key === "ORX") {
    throw new Error("ASSET must be one of OPT, QTC, ORT");
  }
  if (!to || !ethers.isAddress(to)) throw new Error("TO (address) is required");
  if (!amount || BigInt(amount) <= 0n) throw new Error("AMOUNT (>0) is required");

  const token = await lib.attach(key);
  const tx = await token.mint(to, BigInt(amount));
  console.log(`${key} mint tx: ${tx.hash}`);
  const rcpt = await tx.wait();
  console.log(`confirmed in block ${rcpt.blockNumber}`);
  console.log(`balance ${to} = ${await token.balanceOf(to, 0)}`);
}

main().catch((e) => {
  console.error(e.message || e);
  process.exit(1);
});
