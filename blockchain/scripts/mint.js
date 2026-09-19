// Mint OPC into the treasury.
//   TO=0x.. AMOUNT=100 TOKEN_ID=0 make blockchain-mint
const { ethers } = require("hardhat");
const lib = require("./_lib");

async function main() {
  const to = process.env.TO || process.env.TREASURY_ADDRESS;
  const amount = process.env.AMOUNT;
  const tokenId = BigInt(process.env.TOKEN_ID || "0");

  if (!to || !ethers.isAddress(to)) throw new Error("TO (address) is required");
  if (!amount || BigInt(amount) <= 0n) throw new Error("AMOUNT (>0) is required");

  const opc = await lib.getDeployedContract();
  const tx = await opc.mint(to, tokenId, BigInt(amount), "0x");
  console.log(`mint tx: ${tx.hash}`);
  const rcpt = await tx.wait();
  console.log(`confirmed in block ${rcpt.blockNumber}`);
  const bal = await opc.balanceOf(to, tokenId);
  console.log(`balance ${to} [id=${tokenId}] = ${bal}`);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
