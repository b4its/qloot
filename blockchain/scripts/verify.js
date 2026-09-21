const { run, network } = require("hardhat");
const lib = require("./_lib");

// Verify an OryphemCoin (UUPS) deployment.
//
// A UUPS proxy has no constructor and its logic lives in the *implementation*,
// so we verify the implementation (no constructor args) and then let
// hardhat-verify link the proxy to it. Verifying the proxy address directly
// with initialize() args (the old approach) fails with "Already Verified" /
// mismatched args.
async function main() {
  const dep = lib.readDeployment();
  const targets = [
    { label: "implementation", address: dep.implementation, args: [] },
    { label: "proxy", address: dep.address, args: [] },
  ].filter((t) => t.address);

  let failures = 0;
  for (const t of targets) {
    console.log(`Verifying ${t.label} ${t.address} on ${network.name} ...`);
    try {
      await run("verify:verify", { address: t.address, constructorArguments: t.args });
      console.log(`  ${t.label}: verification submitted.`);
    } catch (err) {
      const msg = String(err.message).toLowerCase();
      if (msg.includes("already verified")) {
        console.log(`  ${t.label}: already verified.`);
      } else {
        failures += 1;
        console.error(`  ${t.label}: FAILED — ${err.message}`);
      }
    }
  }
  if (failures) {
    process.exit(1);
  }
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
