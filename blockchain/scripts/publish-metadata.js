// Publish/refresh token metadata and emit a public deployment manifest.
const { ethers, network } = require("hardhat");
const lib = require("./_lib");

async function main() {
  const dep = lib.readDeployment();
  const opc = await lib.attach(dep.address);
  const [signer] = await ethers.getSigners();

  const newUri = process.env.OPC_URI || dep.uri;
  const URI_MANAGER_ROLE = ethers.keccak256(ethers.toUtf8Bytes("URI_MANAGER_ROLE"));
  const canManage = await opc.hasRole(URI_MANAGER_ROLE, signer.address);

  if (canManage && newUri !== dep.uri) {
    console.log(`Setting URI -> ${newUri}`);
    const tx = await opc.setURI(newUri);
    await tx.wait();
    dep.uri = newUri;
    lib.writeDeployment(dep, network.name);
  } else {
    console.log(`URI unchanged (${dep.uri}); caller canManage=${canManage}`);
  }

  const pub = lib.writePublicManifest(dep, network.name);
  console.log("Public manifest written:");
  console.log(JSON.stringify(pub, null, 2));
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
