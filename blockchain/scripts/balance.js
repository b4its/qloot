const { ethers } = require("hardhat");
const lib = require("./_lib");

async function main() {
  const address = process.env.ADDRESS;
  const tokenId = BigInt(process.env.TOKEN_ID || "0");
  if (!address || !ethers.isAddress(address)) throw new Error("ADDRESS is required");
  const opc = await lib.getDeployedContract();
  const bal = await opc.balanceOf(address, tokenId);
  console.log(`balance ${address} [id=${tokenId}] = ${bal}`);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
