// Full on-chain summary of the QLoot digital assets + ORX router.
const { ethers, network } = require("hardhat");
const lib = require("./_lib");

const ROLES = ["OPT", "QTC", "ORT", "ORX"];

async function main() {
  const dep = lib.readDeployment();
  const net = await ethers.provider.getNetwork();

  console.log("========================================");
  console.log(" QLoot — full on-chain summary");
  console.log("========================================");
  console.log(`network  : ${network.name} (chainId=${net.chainId})`);
  console.log(`deployer : ${dep.deployer}`);
  console.log(`admin    : ${dep.admin}`);
  console.log(`treasury : ${dep.treasury}`);
  console.log("----------------------------------------");

  const opt = await lib.attach("OPT", dep);
  const qtc = await lib.attach("QTC", dep);
  const ort = await lib.attach("ORT", dep);
  const orx = await lib.attach("ORX", dep);

  console.log(
    `OPT (OryphemToken)        ${await opt.getAddress()}  supply=${await opt[
      "totalSupply(uint256)"
    ](0)} cap=unlimited`
  );
  console.log(
    `QTC (QlootChain)          ${await qtc.getAddress()}  supply=${await qtc[
      "totalSupply(uint256)"
    ](0)} cap=${await qtc.maxSupply()}`
  );
  console.log(
    `ORT (OryphemIntelligence) ${await ort.getAddress()}  supply=${await ort[
      "totalSupply(uint256)"
    ](0)} cap=unlimited`
  );
  console.log(`ORX (OryphemProxy)        ${await orx.getAddress()}`);
  console.log("----------------------------------------");
  const [optPerOrt, optPerQtc] = await orx.proxyRates();
  console.log(`ORX rates : 1 ORT = ${optPerOrt} OPT · 1 QTC = ${optPerQtc} OPT`);
  console.log(`routed OPT: ${await orx.totalOptSwappedIn()}`);
  console.log(`minted ORT: ${await orx.totalOrtMinted()} · QTC: ${await orx.totalQtcMinted()}`);
  console.log(`aiRequests: ${await orx.totalAiRequests()}`);
  console.log("----------------------------------------");

  // Role overview per asset.
  const roleNames = [
    "MINTER_ROLE",
    "REWARDER_ROLE",
    "PAUSER_ROLE",
    "URI_MANAGER_ROLE",
    "ROUTER_ROLE",
  ];
  for (const key of ["OPT", "QTC", "ORT"]) {
    const token = await lib.attach(key, dep);
    const parts = [];
    for (const rn of roleNames) {
      const r = ethers.keccak256(ethers.toUtf8Bytes(rn));
      const has = await token.hasRole(r, dep.admin);
      if (has) parts.push(rn.replace("_ROLE", ""));
    }
    console.log(`${key} admin roles: ${parts.join(", ")}`);
  }
  console.log("========================================");
}

main().catch((e) => {
  console.error(e.message || e);
  process.exit(1);
});
