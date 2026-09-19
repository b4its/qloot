const { ethers, run, network } = require("hardhat");
const lib = require("./_lib");

async function main() {
  const dep = lib.readDeployment();
  console.log(`Verifying ${dep.address} on ${network.name} ...`);
  try {
    await run("verify:verify", {
      address: dep.address,
      constructorArguments: [
        dep.name,
        dep.symbol,
        dep.uri,
        dep.admin,
      ],
    });
    console.log("Verification submitted.");
  } catch (err) {
    if (String(err.message).toLowerCase().includes("already verified")) {
      console.log("Already verified.");
    } else {
      throw err;
    }
  }
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
