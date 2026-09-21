// Shared helpers for QLoot blockchain scripts.
//
// QLoot ships FOUR separate contracts, each with its own address:
//   OPT  OryphemToken          (ERC-1155 base currency)
//   QTC  QlootChain            (ERC-1155 premium asset, cap 1e15)
//   ORT  OryphemIntelligence   (ERC-1155 AI credit)
//   ORX  OryphemProxy          (asset router: 1 ORT = 50 OPT, 1 QTC = 1000 OPT)
//
// The deployment manifest stores every contract under `contracts[KEY]`, plus a
// flat `address` = the OPT proxy for backwards compatibility.
const fs = require("fs");
const path = require("path");
const { ethers, network } = require("hardhat");

const DEPLOYMENTS_DIR = path.resolve(__dirname, "..", "deployments");
const CONTRACT_NAME = "OryphemToken"; // default/legacy single-contract name

/** Registry of the QLoot contracts deployed together. */
const CONTRACTS = {
  OPT: { name: "OryphemToken", symbol: "OPT" },
  QTC: { name: "QlootChain", symbol: "QTC" },
  ORT: { name: "OryphemIntelligence", symbol: "ORT" },
  ORX: { name: "OryphemProxy", symbol: "ORX" },
};

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
 * Write a PUBLIC manifest (no private material) the backend can consume.
 * Carries the per-asset addresses so the app can talk to each contract.
 */
function writePublicManifest(data, networkName = network.name) {
  fs.mkdirSync(DEPLOYMENTS_DIR, { recursive: true });
  const pub = {
    network: networkName,
    chainId: Number(data.chainId),
    contractName: data.contractName || CONTRACT_NAME,
    standard: data.standard || "ERC-1155 (UUPS proxy)",
    // Flat address = OPT proxy (legacy consumers); full map under `contracts`.
    address: data.address,
    implementation: data.implementation,
    contracts: data.contracts,
    assets: data.assets,
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

/**
 * Attach to a deployed contract by ABI source name.
 * @param {string} address
 * @param {string} abiName Solidity contract name (e.g. "OryphemToken")
 */
async function attachName(address, abiName) {
  const [signer] = await ethers.getSigners();
  const factory = await ethers.getContractFactory(abiName);
  return new ethers.Contract(address, factory.interface.fragments, signer);
}

/**
 * Attach to a QLoot contract.
 * @param {string} key OPT | QTC | ORT | ORX
 * @param {object} [dep] deployment (defaults to the current network manifest)
 */
async function attach(key = "OPT", dep = readDeployment()) {
  const entry = CONTRACTS[key] || { name: key };
  const rec = dep.contracts && dep.contracts[key];
  const address = rec ? rec.address : dep.address;
  const abiName = rec && rec.name ? rec.name : entry.name;
  return attachName(address, abiName);
}

/** Attach to the OPT contract (legacy helper). */
async function getDeployedContract() {
  return attach("OPT");
}

function contractAddress(key, dep = readDeployment()) {
  const rec = dep.contracts && dep.contracts[key];
  return rec ? rec.address : key === "OPT" ? dep.address : undefined;
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
 * Accepts a single record ({address, implementation}) or the full manifest
 * ({contracts:{...}}) and verifies EVERY contract's implementation + proxy.
 *
 * OPT and ORT share identical bytecode (both are thin subclasses of the same
 * base), so hardhat-verify cannot disambiguate them automatically — we always
 * pass the fully-qualified `contract` name.
 */
async function verifyDeployment(dep) {
  const { run, network } = require("hardhat");
  const records = dep.contracts
    ? Object.entries(dep.contracts).map(([key, r]) => ({ label: key, ...r }))
    : [{ label: "OPT", address: dep.address, implementation: dep.implementation }];

  const fqName = (name) => {
    const file =
      name === "OryphemToken"
        ? "OryphemToken.sol"
        : name === "QlootChain"
        ? "QlootChain.sol"
        : name === "OryphemIntelligence"
        ? "OryphemIntelligence.sol"
        : name === "OryphemProxy"
        ? "OryphemProxy.sol"
        : `${name}.sol`;
    return `contracts/${file}:${name}`;
  };

  let failures = 0;
  for (const rec of records) {
    const contract = rec.name ? fqName(rec.name) : undefined;
    for (const [kind, address] of [
      ["implementation", rec.implementation],
      ["proxy", rec.address],
    ]) {
      if (!address) continue;
      const label = `${rec.label} ${kind}`;
      console.log(`Verifying ${label} ${address} on ${network.name} ...`);
      try {
        // The proxy is a generic ERC1967Proxy: let hardhat-verify resolve it.
        const args =
          kind === "proxy"
            ? { address, constructorArguments: [] }
            : { address, constructorArguments: [], contract };
        await run("verify:verify", args);
        console.log(`  ${label}: verification submitted.`);
      } catch (err) {
        const msg = String(err.message).toLowerCase();
        if (msg.includes("already verified")) {
          console.log(`  ${label}: already verified.`);
        } else {
          failures += 1;
          console.error(`  ${label}: FAILED — ${err.message}`);
        }
      }
    }
  }
  return failures;
}

module.exports = {
  DEPLOYMENTS_DIR,
  CONTRACT_NAME,
  CONTRACTS,
  deploymentFile,
  manifestFile,
  readDeployment,
  writeDeployment,
  writePublicManifest,
  attach,
  attachName,
  getDeployedContract,
  contractAddress,
  toBytes32,
  explorerUrl,
  verifyDeployment,
};
