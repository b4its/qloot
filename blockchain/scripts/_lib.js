// Shared helpers for QLoot blockchain scripts.
const fs = require("fs");
const path = require("path");
const { ethers, network } = require("hardhat");

const DEPLOYMENTS_DIR = path.resolve(__dirname, "..", "deployments");
const CONTRACT_NAME = "OryphemCoin";

function deploymentFile(networkName) {
  return path.join(DEPLOYMENTS_DIR, `${networkName}.json`);
}

function manifestFile(networkName) {
  return path.join(DEPLOYMENTS_DIR, `${networkName}.public.json`);
}

function readDeployment(networkName = network.name) {
  const file = deploymentFile(networkName);
  if (!fs.existsSync(file)) {
    throw new Error(
      `No deployment manifest for network "${networkName}" (${file}). Run deploy first.`
    );
  }
  return JSON.parse(fs.readFileSync(file, "utf8"));
}

function writeDeployment(data, networkName = network.name) {
  fs.mkdirSync(DEPLOYMENTS_DIR, { recursive: true });
  fs.writeFileSync(deploymentFile(networkName), JSON.stringify(data, null, 2));
}

/**
 * Write a PUBLIC manifest (no private material) that the backend can consume.
 * Only addresses, chain id and ABI-relevant info — never keys.
 */
function writePublicManifest(data, networkName = network.name) {
  fs.mkdirSync(DEPLOYMENTS_DIR, { recursive: true });
  const pub = {
    network: networkName,
    chainId: Number(data.chainId),
    contractName: data.contractName || CONTRACT_NAME,
    standard: data.standard || "ERC-1155",
    address: data.address,
    implementation: data.implementation,
    treasury: data.treasury,
    tokenId: data.tokenId ?? 0,
    uri: data.uri,
    admin: data.admin,
    deployer: data.deployer,
    txHash: data.txHash,
    blockNumber: data.blockNumber,
    deployedAt: data.deployedAt,
    upgradedAt: data.upgradedAt,
  };
  fs.writeFileSync(manifestFile(networkName), JSON.stringify(pub, null, 2));
  return pub;
}

async function attach(address) {
  const [signer] = await ethers.getSigners();
  const factory = await ethers.getContractFactory(CONTRACT_NAME);
  // Use the plain Contract (not the factory wrapper) so all ABI functions,
  // including `uri(uint256)`, are directly callable.
  return new ethers.Contract(address, factory.interface.fragments, signer);
}

async function getDeployedContract() {
  const dep = readDeployment();
  return attach(dep.address);
}

function toBytes32(value) {
  if (!value) return ethers.ZeroHash;
  if (ethers.isHexString(value, 32)) return value;
  return ethers.keccak256(ethers.toUtf8Bytes(value));
}

function explorerUrl(chainId, txHash) {
  if (Number(chainId) === 11155111) return `https://sepolia.etherscan.io/tx/${txHash}`;
  return null;
}

/**
 * Verify the implementation and the proxy of a UUPS deployment on Etherscan.
 *
 * A UUPS proxy has no constructor and its logic lives in the *implementation*,
 * so the implementation is verified first (no constructor args), then the proxy
 * (hardhat-verify links it to the implementation). "Already verified" is treated
 * as success. Returns the number of unexpected failures.
 */
async function verifyDeployment(dep) {
  const { run, network } = require("hardhat");
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
  return failures;
}

module.exports = {
  DEPLOYMENTS_DIR,
  CONTRACT_NAME,
  deploymentFile,
  manifestFile,
  readDeployment,
  writeDeployment,
  writePublicManifest,
  attach,
  getDeployedContract,
  toBytes32,
  explorerUrl,
  verifyDeployment,
};
