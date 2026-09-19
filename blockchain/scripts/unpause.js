const lib = require("./_lib");

async function main() {
  const opc = await lib.getDeployedContract();
  const tx = await opc.unpause();
  console.log(`unpause tx: ${tx.hash}`);
  await tx.wait();
  console.log(`paused = ${await opc.paused()}`);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
