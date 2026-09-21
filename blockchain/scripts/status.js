// Print a status summary of all four QLoot contracts.
const { ethers, network } = require("hardhat");
const lib = require("./_lib");

async function main() {
  const dep = lib.readDeployment();
  const net = await ethers.provider.getNetwork();
  const [signer] = await ethers.getSigners();
  const bal = await ethers.provider.getBalance(signer.address);

  const opt = await lib.attach("OPT", dep);
  const qtc = await lib.attach("QTC", dep);
  const ort = await lib.attach("ORT", dep);
  const orx = await lib.attach("ORX", dep);

  console.log("========================================");
  console.log(" QLoot — digital assets status");
  console.log("========================================");
  console.log(`network  : ${network.name} (chainId=${net.chainId})`);
  console.log(`treasury : ${dep.treasury}`);
  console.log("----------------------------------------");
  console.log(`OPT OryphemToken         : ${await opt.getAddress()}`);
  console.log(`    name/symbol          : ${await opt.name()} / ${await opt.symbol()}`);
  console.log(`    supply               : ${await opt["totalSupply(uint256)"](0)} (unlimited)`);
  console.log(`    paused               : ${await opt.paused()}`);
  console.log(`QTC QlootChain           : ${await qtc.getAddress()}`);
  console.log(`    name/symbol          : ${await qtc.name()} / ${await qtc.symbol()}`);
  console.log(
    `    supply / cap         : ${await qtc["totalSupply(uint256)"](0)} / ${await qtc.maxSupply()}`
  );
  console.log(`ORT OryphemIntelligence  : ${await ort.getAddress()}`);
  console.log(`    name/symbol          : ${await ort.name()} / ${await ort.symbol()}`);
  console.log(`    supply               : ${await ort["totalSupply(uint256)"](0)} (unlimited)`);
  console.log(`ORX OryphemProxy         : ${await orx.getAddress()}`);
  const [optPerOrt, optPerQtc] = await orx.proxyRates();
  console.log(`    rates                : 1 ORT = ${optPerOrt} OPT · 1 QTC = ${optPerQtc} OPT`);
  console.log(`    aiRequests           : ${await orx.totalAiRequests()}`);
  console.log("----------------------------------------");
  console.log(`signer   : ${signer.address}`);
  console.log(`signer ETH: ${ethers.formatEther(bal)}`);
  const explorer = lib.explorerUrl(net.chainId, dep.txHash);
  if (explorer) console.log(`deploy tx: ${explorer}`);
  console.log("========================================");
}

main().catch((e) => {
  console.error(e.message || e);
  process.exit(1);
});
