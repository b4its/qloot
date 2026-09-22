const { network } = require("hardhat");
const lib = require("./_lib");

// Verify the QLoot contracts (OPT/QTC/ORT + ORX) on Etherscan.
//
// Every contract is a UUPS proxy, so we verify each implementation (no
// constructor args) and let hardhat-verify link the proxy to it. Verifying the
// proxy with initialize() args (the old approach) fails with "Already
// Verified" / mismatched args.
async function main() {
  const dep = lib.readDeployment();
  const local = ["hardhat", "localhost", "anvil"].includes(network.name);
  if (local) {
    console.log(
      `Nothing to verify on the local network "${network.name}" — Etherscan ` +
        `verification only applies to public networks. Deploy with ` +
        `NETWORK=sepolia CONFIRM_SEPOLIA=yes and verification runs automatically.`
    );
    return;
  }
  const failures = await lib.verifyDeployment(dep);
  if (failures) {
    process.exit(1);
  }
}

main().catch((e) => {
  console.error(e.message || e);
  process.exit(1);
});
