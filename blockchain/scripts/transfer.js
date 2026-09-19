// Transfer OPC.
//   TO=0x.. AMOUNT=10 TOKEN_ID=0 make blockchain-transfer
const { ethers } = require("hardhat");
const lib = require("./_lib");

async function main() {
  const to = process.env.TO;
  const amount = process.env.AMOUNT;
  const tokenId = BigInt(process.env.TOKEN_ID || "0");

  if (!to || !ethers.isAddress(to)) throw new Error("TO (address) is required");
  if (!amount || BigInt(amount) <= 0n) throw new Error("AMOUNT (>0) is required");

  const opc = await lib.getDeployedContract();
  const tx = await opc.safeTransferFrom(process.env.FROM || (await ethers.getSigners())[0].address, to, tokenId, BigInt(amount), "0x");
  console.log(`transfer tx: ${tx.hash}`);
  await tx.wait();
  console.log(`new balance ${to} = ${await opc.balanceOf(to, tokenId)}`);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
