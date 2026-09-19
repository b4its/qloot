// Upgrade the existing OPC proxy to a new implementation and run the
// reinitializer. Preserves all storage (balances, XP, badges, courses).
//
//   NETWORK=localhost make blockchain-upgrade
//   NETWORK=sepolia CONFIRM_SEPOLIA=yes make blockchain-upgrade
const { ethers, network, upgrades } = require("hardhat");
const lib = require("./_lib");

async function main() {
  const dep = lib.readDeployment();
  const [deployer] = await ethers.getSigners();

  console.log("----------------------------------------");
  console.log(`Network : ${network.name}`);
  console.log(`Proxy   : ${dep.address}`);
  console.log(`Upgrader: ${deployer.address}`);
  console.log("----------------------------------------");

  const Factory = await ethers.getContractFactory(lib.CONTRACT_NAME);
  const upgraded = await upgrades.upgradeProxy(dep.address, Factory, {
    kind: "uups",
    call: {
      fn: "initializeV2",
      args: [dep.admin || deployer.address, dep.treasury || deployer.address],
    },
  });
  await upgraded.waitForDeployment();

  const implAddress = await upgrades.erc1967.getImplementationAddress(dep.address);
  dep.implementation = implAddress;
  dep.upgradedAt = new Date().toISOString();
  dep.upgradedBy = deployer.address;
  lib.writeDeployment(dep, network.name);
  lib.writePublicManifest(dep, network.name);

  console.log(`New implementation: ${implAddress}`);
  console.log("Upgrade complete; storage preserved and initializeV2 executed.");
  return dep.address;
}

main()
  .then(() => process.exit(0))
  .catch((err) => {
    console.error(err);
    process.exit(1);
  });
