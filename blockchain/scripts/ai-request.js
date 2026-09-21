// ORX (OryphemProxy): pay for AI usage with ORT (1 request = 1 ORT).
//   REQUESTS=1 make blockchain-ai-request
const { ethers } = require("hardhat");
const lib = require("./_lib");

async function main() {
  const requests = process.env.REQUESTS;
  if (!requests || BigInt(requests) <= 0n) throw new Error("REQUESTS (>0) is required");

  const orx = await lib.attach("ORX");
  const signer = (await ethers.getSigners())[0];

  console.log(`Paying ${requests} AI request(s) with ORT ...`);
  const tx = await orx.payAiRequest(BigInt(requests));
  console.log(`aiRequest tx: ${tx.hash}`);
  await tx.wait();

  const ort = await lib.attach("ORT");
  console.log(`ORT balance   = ${await ort.balanceOf(signer.address, 0)}`);
  console.log(`totalRequests = ${await orx.totalAiRequests()}`);
}

main().catch((e) => {
  console.error(e.message || e);
  process.exit(1);
});
