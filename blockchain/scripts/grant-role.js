// Grant a role: ROLE=MINTER_ROLE ADDRESS=0x.. make blockchain-grant-role
const { ethers } = require("hardhat");
const lib = require("./_lib");

const VALID = [
  "MINTER_ROLE",
  "REWARDER_ROLE",
  "PAUSER_ROLE",
  "URI_MANAGER_ROLE",
  "DEFAULT_ADMIN_ROLE",
];

async function main() {
  const roleName = process.env.ROLE;
  const address = process.env.ADDRESS;
  if (!VALID.includes(roleName)) throw new Error(`ROLE must be one of ${VALID.join(", ")}`);
  if (!address || !ethers.isAddress(address)) throw new Error("ADDRESS is required");

  const opc = await lib.getDeployedContract();
  const role =
    roleName === "DEFAULT_ADMIN_ROLE"
      ? ethers.ZeroHash
      : ethers.keccak256(ethers.toUtf8Bytes(roleName));
  const tx = await opc.grantRole(role, address);
  console.log(`grant tx: ${tx.hash}`);
  await tx.wait();
  console.log(`${roleName} granted to ${address}`);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
