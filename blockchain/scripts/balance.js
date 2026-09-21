// Show an account's balance of a QLoot asset.
//   ASSET=OPT ADDRESS=0x.. make blockchain-balance
const { ethers } = require("hardhat");
const lib = require("./_lib");

async function main() {
  const key = (process.env.ASSET || "OPT").toUpperCase();
  const address = process.env.ADDRESS;
  if (!lib.CONTRACTS[key] || key === "ORX") {
    throw new Error("ASSET must be one of OPT, QTC, ORT");
  }
  if (!address || !ethers.isAddress(address)) throw new Error("ADDRESS is required");

  const token = await lib.attach(key);
  const bal = await token.balanceOf(address, 0);
  console.log(`${key} balance ${address} = ${bal}`);
}

main().catch((e) => {
  console.error(e.message || e);
  process.exit(1);
});
