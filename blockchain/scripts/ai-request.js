// ORX (OryphemProxy): pay for AI usage with ORT (1 request = 1 ORT).
//   REQUESTS=1 make blockchain-ai-request
const { ethers } = require("hardhat");
const lib = require("./_lib");

async function main() {
  const requests = process.env.REQUESTS;
  if (!requests || BigInt(requests) <= 0n) throw new Error("REQUESTS (>0) is required");

  const token = await lib.getDeployedContract();
  const signer = (await ethers.getSigners())[0];

  console.log(`Paying ${requests} AI request(s) with ORT ...`);
  const tx = await token.payAiRequest(BigInt(requests));
  console.log(`aiRequest tx: ${tx.hash}`);
  await tx.wait();

  console.log(`ORT balance   = ${await token.balanceOf(signer.address, 2)}`);
  console.log(`aiRequestsOf  = ${await token.aiRequestsOf(signer.address)}`);
  console.log(`totalRequests = ${await token.totalAiRequests()}`);
}

main().catch((e) => {
  console.error(e.message || e);
  process.exit(1);
});
