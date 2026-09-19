// Shared helpers for QLoot blockchain scripts.
const fs = require("fs");
const path = require("path");
const { ethers, network } = require("hardhat");

const DEPLOYMENTS_DIR = path.resolve(__dirname, "..", "deployments");
const CONTRACT_NAME = "OryphemCoin1155";

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
    address: data.address,
    treasury: data.treasury,
    tokenId: data.tokenId ?? 0,
    uri: data.uri,
    deployer: data.deployer,
    txHash: data.txHash,
    blockNumber: data.blockNumber,
    deployedAt: data.deployedAt,
  };
  fs.writeFileSync(manifestFile(networkName), JSON.stringify(pub, null, 2));
  return pub;
}

async function attach(address) {
  const factory = await ethers.getContractFactory(CONTRACT_NAME);
  return factory.attach(address);
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
};
