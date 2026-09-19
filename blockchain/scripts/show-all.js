const { ethers, network } = require("hardhat");
const lib = require("./_lib");

const ROLES = ["ADMIN_ROLE", "MINTER_ROLE", "REWARDER_ROLE", "PAUSER_ROLE", "URI_MANAGER_ROLE"];

async function main() {
  const dep = lib.readDeployment();
  const net = await ethers.provider.getNetwork();
  const opc = await lib.attach(dep.address);

  console.log("========================================");
  console.log(" QLoot — full on-chain summary");
  console.log("========================================");
  console.log(`network        : ${network.name} (chainId=${net.chainId})`);
  console.log(`contract       : ${dep.address}`);
  console.log(`deployer       : ${dep.deployer}`);
  console.log(`admin          : ${dep.admin}`);
  console.log(`treasury       : ${dep.treasury}`);
  console.log(`uri            : ${await opc.getFunction("uri").staticCall(0)}`);
  console.log(`paused         : ${await opc.paused()}`);
  console.log("----------------------------------------");
  console.log(`totalSupply(0) : ${await opc["totalSupply(uint256)"](0)}`);
  console.log(`treasuryBal(0) : ${await opc.balanceOf(dep.treasury, 0)}`);
  console.log(`totalMinted    : ${await opc.totalMinted()}`);
  console.log(`totalBurned    : ${await opc.totalBurned()}`);
  console.log(`totalCourses   : ${await opc.totalCourses()}`);
  console.log(`totalXp        : ${await opc.totalXpDistributed()}`);
  console.log("----------------------------------------");
  console.log("Roles:");
  const DEFAULT_ADMIN = ethers.ZeroHash;
  for (const name of ["DEFAULT_ADMIN_ROLE", ...ROLES]) {
    const role =
      name === "DEFAULT_ADMIN_ROLE" ? DEFAULT_ADMIN : ethers.keccak256(ethers.toUtf8Bytes(name));
    const hasAdmin = await opc.hasRole(role, dep.admin);
    const hasDeployer = await opc.hasRole(role, dep.deployer);
    console.log(`  ${name.padEnd(18)} admin=${hasAdmin} deployer=${hasDeployer}`);
  }
  console.log("----------------------------------------");
  const explorer = lib.explorerUrl(net.chainId, dep.txHash);
  console.log(`deploy tx      : ${explorer || dep.txHash}`);
  console.log("========================================");
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
