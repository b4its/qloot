// Upgrade one (or all) QLoot proxies to their latest implementation.
//
//   ASSET=OPT make blockchain-upgrade           # upgrade OPT only
//   ASSET=ALL make blockchain-upgrade           # upgrade OPT, QTC, ORT, ORX
const { ethers, network, upgrades } = require("hardhat");
const lib = require("./_lib");

async function main() {
  const dep = lib.readDeployment();
  const [deployer] = await ethers.getSigners();
  const target = (process.env.ASSET || "ALL").toUpperCase();

  const keys = target === "ALL" ? Object.keys(lib.CONTRACTS) : [target];
  for (const key of keys) {
    if (!lib.CONTRACTS[key])
      throw new Error(`ASSET must be one of ${Object.keys(lib.CONTRACTS).join(", ")}, or ALL`);
  }

  console.log("----------------------------------------");
  console.log(`Network : ${network.name}`);
  console.log(`Upgrader: ${deployer.address}`);
  console.log(`Target  : ${keys.join(", ")}`);
  console.log("----------------------------------------");

  for (const key of keys) {
    const rec = dep.contracts && dep.contracts[key];
    if (!rec) {
      console.warn(`skip ${key}: no address in manifest`);
      continue;
    }
    const Factory = await ethers.getContractFactory(rec.name || lib.CONTRACTS[key].name);
    const upgraded = await upgrades.upgradeProxy(rec.address, Factory, { kind: "uups" });
    await upgraded.waitForDeployment();
    const impl = await upgrades.erc1967.getImplementationAddress(rec.address);
    rec.implementation = impl;
    console.log(`${key} upgraded -> implementation ${impl}`);
  }

  dep.contracts = dep.contracts || {};
  dep.upgradedAt = new Date().toISOString();
  if (dep.contracts.OPT) {
    dep.implementation = dep.contracts.OPT.implementation;
    dep.address = dep.contracts.OPT.address;
  }
  lib.writeDeployment(dep, network.name);
  lib.writePublicManifest(dep, network.name);
  console.log("Upgrade complete; storage preserved.");
}

main()
  .then(() => process.exit(0))
  .catch((err) => {
    console.error(err.message || err);
    process.exit(1);
  });
