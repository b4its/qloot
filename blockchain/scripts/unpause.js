// Unpause a QLoot asset (default ASSET=OPT).
const lib = require("./_lib");

async function main() {
  const key = (process.env.ASSET || "OPT").toUpperCase();
  if (!lib.CONTRACTS[key] || key === "ORX") throw new Error("ASSET must be one of OPT, QTC, ORT");
  const token = await lib.attach(key);
  const tx = await token.unpause();
  console.log(`${key} unpause tx: ${tx.hash}`);
  await tx.wait();
  console.log(`${key} paused = ${await token.paused()}`);
}

main().catch((e) => {
  console.error(e.message || e);
  process.exit(1);
});
