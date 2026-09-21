const { ethers, network } = require("hardhat");
const lib = require("./_lib");

async function main() {
  const dep = lib.readDeployment();
  const net = await ethers.provider.getNetwork();
  const opc = await lib.attach(dep.address);
  const [signer] = await ethers.getSigners();
  const bal = await ethers.provider.getBalance(signer.address);

  console.log("========================================");
  console.log(" QLoot — OryphemToken status");
  console.log("========================================");
  console.log(`network        : ${network.name} (chainId=${net.chainId})`);
  console.log(`contract       : ${dep.address}`);
  console.log(`name / symbol  : ${await opc.name()} / ${await opc.symbol()}`);
  console.log(`uri            : ${await opc.getFunction("uri").staticCall(0)}`);
  console.log(`treasury       : ${dep.treasury}`);
  console.log(`OPT supply     : ${await opc["totalSupply(uint256)"](0)} (unlimited)`);
  console.log(
    `QTC supply     : ${await opc["totalSupply(uint256)"](1)} / cap ${await opc.maxSupplyOf(1)}`
  );
  console.log(`ORT supply     : ${await opc["totalSupply(uint256)"](2)} (unlimited)`);
  console.log(`treasuryBal(OPT): ${await opc.balanceOf(dep.treasury, 0)}`);
  console.log(`paused         : ${await opc.paused()}`);
  console.log(`maxMintPerTx   : ${await opc.maxMintPerTx()}`);
  console.log(`dailyMintCap   : ${await opc.dailyMintCap()}`);
  console.log(`aiRequests     : ${await opc.totalAiRequests()}`);
  console.log(`signer         : ${signer.address}`);
  console.log(`signer ETH     : ${ethers.formatEther(bal)}`);
  const explorer = lib.explorerUrl(net.chainId, dep.txHash);
  if (explorer) console.log(`deploy tx      : ${explorer}`);
  console.log("========================================");
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
