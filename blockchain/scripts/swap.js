// ORX (OryphemProxy): swap OPT -> QTC/ORT at the fixed proxy rate.
//   ASSET=ORT AMOUNT=10 make blockchain-swap   # buy 10 ORT for 500 OPT
//   ASSET=QTC AMOUNT=2  make blockchain-swap   # buy 2 QTC for 2000 OPT
const { ethers } = require("hardhat");
const lib = require("./_lib");

// asset id used by the router: 1 = QTC, 2 = ORT.
const ROUTER_ID = { QTC: 1n, ORT: 2n };

async function main() {
  const key = (process.env.ASSET || "ORT").toUpperCase();
  const amount = process.env.AMOUNT;
  const assetId = ROUTER_ID[key];

  if (!assetId) throw new Error("ASSET must be ORT or QTC");
  if (!amount || BigInt(amount) <= 0n) throw new Error("AMOUNT (>0) is required");

  const orx = await lib.attach("ORX");
  const [optPerOrt, optPerQtc] = await orx.proxyRates();
  const rate = key === "ORT" ? optPerOrt : optPerQtc;
  const cost = rate * BigInt(amount);

  console.log(`Swapping ${cost} OPT -> ${amount} ${key} (rate ${rate} OPT/unit) ...`);
  const tx = await orx.swapOptFor(assetId, BigInt(amount));
  console.log(`swap tx: ${tx.hash}`);
  await tx.wait();

  const signer = (await ethers.getSigners())[0];
  const opt = await lib.attach("OPT");
  const target = await lib.attach(key);
  console.log(`balance OPT = ${await opt.balanceOf(signer.address, 0)}`);
  console.log(`balance ${key} = ${await target.balanceOf(signer.address, 0)}`);
}

main().catch((e) => {
  console.error(e.message || e);
  process.exit(1);
});
