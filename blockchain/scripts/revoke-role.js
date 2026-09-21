// Revoke a role on a QLoot asset.
//   ASSET=OPT ROLE=MINTER_ROLE ADDRESS=0x.. make blockchain-revoke-role
const { ethers } = require("hardhat");
const lib = require("./_lib");

const VALID = [
  "MINTER_ROLE",
  "REWARDER_ROLE",
  "PAUSER_ROLE",
  "URI_MANAGER_ROLE",
  "ROUTER_ROLE",
  "ADMIN_ROLE",
  "DEFAULT_ADMIN_ROLE",
];

async function main() {
  const key = (process.env.ASSET || "OPT").toUpperCase();
  const roleName = process.env.ROLE;
  const address = process.env.ADDRESS;
  if (!lib.CONTRACTS[key] || key === "ORX") throw new Error("ASSET must be one of OPT, QTC, ORT");
  if (!VALID.includes(roleName)) throw new Error(`ROLE must be one of ${VALID.join(", ")}`);
  if (!address || !ethers.isAddress(address)) throw new Error("ADDRESS is required");

  const token = await lib.attach(key);
  const role =
    roleName === "DEFAULT_ADMIN_ROLE"
      ? ethers.ZeroHash
      : ethers.keccak256(ethers.toUtf8Bytes(roleName));
  const tx = await token.revokeRole(role, address);
  console.log(`revoke tx: ${tx.hash}`);
  await tx.wait();
  console.log(`${roleName} revoked from ${address} on ${key}`);
}

main().catch((e) => {
  console.error(e.message || e);
  process.exit(1);
});
