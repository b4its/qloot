const { ethers, network } = require("hardhat");
const lib = require("./_lib");

async function main() {
  const dep = lib.readDeployment();
  const net = await ethers.provider.getNetwork();
  const opc = lib.attach(dep.address);
  const [signer] = await ethers.getSigners();
  const bal = await ethers.provider.getBalance(signer.address);

  console.log("========================================");
  console.log(" QLoot — OryphemCoin status");
  console.log("========================================");
  console.log(`network        : ${network.name} (chainId=${net.chainId})`);
  console.log(`contract       : ${dep.address}`);
  console.log(`name / symbol  : ${await opc.name()} / ${await opc.symbol()}`);
  console.log(`uri            : ${await opc.uri(0)}`);
  console.log(`treasury       : ${dep.treasury}`);
  console.log(`totalSupply(0) : ${await opc["totalSupply(uint256)"](0)}`);
  console.log(`treasuryBal(0) : ${await opc.balanceOf(dep.treasury, 0)}`);
  console.log(`paused         : ${await opc.paused()}`);
  console.log(`maxMintPerTx   : ${await opc.maxMintPerTx()}`);
  console.log(`dailyMintCap   : ${await opc.dailyMintCap()}`);
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
