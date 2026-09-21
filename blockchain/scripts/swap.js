// ORX (OryphemProxy): swap OPT -> another asset at the fixed proxy rate.
//   ASSET=2 AMOUNT=10 make blockchain-swap   # buy 10 ORT for 500 OPT
//   ASSET=1 AMOUNT=2  make blockchain-swap   # buy 2 QTC for 2000 OPT
const { ethers } = require("hardhat");
const lib = require("./_lib");

async function main() {
  const asset = BigInt(process.env.ASSET || "0");
  const amount = process.env.AMOUNT;

  if (asset !== 1n && asset !== 2n) throw new Error("ASSET must be 1 (QTC) or 2 (ORT)");
  if (!amount || BigInt(amount) <= 0n) throw new Error("AMOUNT (>0) is required");

  const token = await lib.getDeployedContract();
  const [optPerOrt, optPerQtc] = await token.proxyRates();
  const rate = asset === 2n ? optPerOrt : optPerQtc;
  const cost = rate * BigInt(amount);

  console.log(
    `Swapping ${cost} OPT -> ${amount} ${asset === 2n ? "ORT" : "QTC"} (rate ${rate} OPT/unit) ...`
  );
  const tx = await token.swapOptFor(asset, BigInt(amount));
  console.log(`swap tx: ${tx.hash}`);
  await tx.wait();
  const signer = (await ethers.getSigners())[0];
  console.log(`balance OPT = ${await token.balanceOf(signer.address, 0)}`);
  console.log(`balance ${asset === 2n ? "ORT" : "QTC"} = ${await token.balanceOf(signer.address, asset)}`);
}

main().catch((e) => {
  console.error(e.message || e);
  process.exit(1);
});
