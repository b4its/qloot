// Set the ERC-1155 metadata URI on every QLoot asset and refresh the manifest.
//   OPT_URI="https://metadata.qloot.example/{id}.json" make blockchain-publish
const { ethers, network } = require("hardhat");
const lib = require("./_lib");

async function main() {
  const dep = lib.readDeployment();
  const [signer] = await ethers.getSigners();
  const newUri = process.env.OPT_URI || dep.uri;
  const URI_MANAGER_ROLE = ethers.keccak256(ethers.toUtf8Bytes("URI_MANAGER_ROLE"));

  for (const key of ["OPT", "QTC", "ORT"]) {
    const token = await lib.attach(key, dep);
    const canManage = await token.hasRole(URI_MANAGER_ROLE, signer.address);
    if (canManage && newUri) {
      console.log(`${key}: setting URI -> ${newUri}`);
      const tx = await token.setURI(newUri);
      await tx.wait();
    } else {
      console.log(`${key}: URI unchanged (canManage=${canManage})`);
    }
  }

  dep.uri = newUri;
  lib.writeDeployment(dep, network.name);
  const pub = lib.writePublicManifest(dep, network.name);
  console.log("Public manifest written:");
  console.log(JSON.stringify(pub, null, 2));
}

main().catch((e) => {
  console.error(e.message || e);
  process.exit(1);
});
