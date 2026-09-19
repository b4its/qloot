// Register a badge (metadata) on the OPC contract.
//   BADGE_ID=1 BADGE_URI="ipfs://..." SOULBOUND=true make blockchain-create-badge
const lib = require("./_lib");

async function main() {
  const badgeId = Number(process.env.BADGE_ID || "0");
  if (!badgeId) throw new Error("BADGE_ID is required");
  const uri = process.env.BADGE_URI || "";
  const soulbound = (process.env.SOULBOUND || "false") === "true";
  const opc = await lib.getDeployedContract();
  const tx = await opc.registerBadge(badgeId, uri, soulbound);
  console.log(`registerBadge tx: ${tx.hash}`);
  await tx.wait();
  console.log(`badge ${badgeId} registered (soulbound=${soulbound}).`);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
