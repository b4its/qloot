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
  const failures = await lib.verifyDeployment(dep);
  if (failures) {
    process.exit(1);
  }
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
