// Deploy the QLoot digital assets (UUPS proxies):
//   OPT  OryphemToken          (ERC-1155 base currency, unlimited)
//   QTC  QlootChain            (ERC-1155 premium asset, cap 1e15)
//   ORT  OryphemIntelligence   (ERC-1155 AI credit)
//   ORX  OryphemProxy          (router: 1 ORT = 50 OPT, 1 QTC = 1000 OPT)
//
// Secret handling: the deployer key is read from BLOCKCHAIN_PRIVATE_KEY via the
// hardhat network config. It is never accepted as a CLI argument.
//
//   NETWORK=localhost make blockchain-deploy
//   NETWORK=sepolia CONFIRM_SEPOLIA=yes make blockchain-deploy
//
// After a successful deploy on a public network every implementation + proxy is
// verified on Etherscan automatically (AUTO_VERIFY=false to skip).
const { ethers, network, upgrades } = require("hardhat");
const lib = require("./_lib");

const OPT_NAME = process.env.OPT_NAME || "OryphemToken";
const OPT_SYMBOL = process.env.OPT_SYMBOL || "OPT";
const QTC_NAME = process.env.QTC_NAME || "QlootChain";
const QTC_SYMBOL = process.env.QTC_SYMBOL || "QTC";
const ORT_NAME = process.env.ORT_NAME || "OryphemIntelligence";
const ORT_SYMBOL = process.env.ORT_SYMBOL || "ORT";
const OPT_URI = process.env.OPT_URI || "https://metadata.qloot.example/{id}.json";

async function deployProxy(factoryName, args, label) {
  const Factory = await ethers.getContractFactory(factoryName);
  const proxy = await upgrades.deployProxy(Factory, args, {
    kind: "uups",
    initializer: "initialize",
  });
  await proxy.waitForDeployment();
  const address = await proxy.getAddress();
  const impl = await upgrades.erc1967.getImplementationAddress(address);
  const tx = proxy.deploymentTransaction();
  const receipt = tx ? await tx.wait() : null;
  console.log(`${label} proxy         : ${address}`);
  console.log(`${label} implementation: ${impl}`);
  return {
    name: factoryName,
    address,
    implementation: impl,
    txHash: tx ? tx.hash : null,
    blockNumber: receipt ? receipt.blockNumber : null,
  };
}

async function main() {
  const [deployer] = await ethers.getSigners();
  const net = await ethers.provider.getNetwork();
  const chainId = Number(net.chainId);

  const admin = process.env.OPT_ADMIN_ADDRESS || deployer.address;
  const treasury = process.env.TREASURY_ADDRESS || deployer.address;

  console.log("----------------------------------------");
  console.log(`Network  : ${network.name} (chainId=${chainId})`);
  console.log(`Deployer : ${deployer.address}`);
  console.log(`Admin    : ${admin}`);
  console.log(`Treasury : ${treasury}`);
  console.log(`URI      : ${OPT_URI}`);
  console.log("----------------------------------------");

  // 1) The three ERC-1155 assets.
  const opt = await deployProxy(
    lib.CONTRACTS.OPT.name,
    [OPT_NAME, OPT_SYMBOL, OPT_URI, admin],
    "OPT"
  );
  const qtc = await deployProxy(
    lib.CONTRACTS.QTC.name,
    [QTC_NAME, QTC_SYMBOL, OPT_URI, admin],
    "QTC"
  );
  const ort = await deployProxy(
    lib.CONTRACTS.ORT.name,
    [ORT_NAME, ORT_SYMBOL, OPT_URI, admin],
    "ORT"
  );

  // 2) The OryphemProxy router wired to the three assets.
  const orx = await deployProxy(
    lib.CONTRACTS.ORX.name,
    [admin, opt.address, qtc.address, ort.address, treasury],
    "ORX"
  );

  // 3) Grant the router ROUTER_ROLE on each asset so it can settle swaps.
  const ROUTER_ROLE = ethers.keccak256(ethers.toUtf8Bytes("ROUTER_ROLE"));
  for (const [key, rec] of [
    ["OPT", opt],
    ["QTC", qtc],
    ["ORT", ort],
  ]) {
    const asset = await lib.attachName(rec.address, rec.name);
    const tx = await asset.grantRole(ROUTER_ROLE, orx.address);
    await tx.wait();
    console.log(`Granted ROUTER_ROLE on ${key} to ORX (${orx.address})`);
  }

  const record = {
    contractName: lib.CONTRACT_NAME,
    standard: "ERC-1155 (UUPS proxy) multi-contract",
    name: OPT_NAME,
    symbol: OPT_SYMBOL,
    uri: OPT_URI,
    // Flat = OPT, for legacy consumers.
    address: opt.address,
    implementation: opt.implementation,
    contracts: {
      OPT: { ...opt, symbol: OPT_SYMBOL, role: "base currency (unlimited)" },
      QTC: { ...qtc, symbol: QTC_SYMBOL, role: "premium chain asset (cap 1e15)" },
      ORT: { ...ort, symbol: ORT_SYMBOL, role: "AI credit (1 request = 1 ORT)" },
      ORX: { ...orx, role: "OryphemProxy router (1 ORT = 50 OPT, 1 QTC = 1000 OPT)" },
    },
    assets: [
      { key: "OPT", id: 0, symbol: OPT_SYMBOL, name: OPT_NAME, role: "base currency (unlimited)" },
      {
        key: "QTC",
        id: 1,
        symbol: QTC_SYMBOL,
        name: QTC_NAME,
        role: "premium chain asset (cap 1e15)",
      },
      { key: "ORT", id: 2, symbol: ORT_SYMBOL, name: ORT_NAME, role: "AI credit (1 req = 1 ORT)" },
      { key: "ORX", id: null, symbol: "ORX", name: "OryphemProxy", role: "router" },
    ],
    deployer: deployer.address,
    admin,
    treasury,
    tokenId: 0,
    chainId,
    network: network.name,
    txHash: opt.txHash,
    blockNumber: opt.blockNumber,
    deployedAt: new Date().toISOString(),
  };

  lib.writeDeployment(record, network.name);
  lib.writePublicManifest(record, network.name);

  console.log("----------------------------------------");
  console.log(`OPT  OryphemToken        : ${opt.address}`);
  console.log(`QTC  QlootChain          : ${qtc.address}`);
  console.log(`ORT  OryphemIntelligence : ${ort.address}`);
  console.log(`ORX  OryphemProxy        : ${orx.address}`);
  console.log(`manifest: deployments/${network.name}.json`);
  console.log("----------------------------------------");

  // Auto-verify on public networks (Etherscan API v2).
  const isLocal = ["hardhat", "localhost", "anvil"].includes(network.name);
  const shouldVerify = !isLocal && process.env.AUTO_VERIFY !== "false";
  if (shouldVerify) {
    console.log("");
    console.log("Verifying on Etherscan ...");
    // Small wait so Etherscan has indexed the bytecode before verifying.
    await new Promise((r) => setTimeout(r, 20000));
    const failures = await lib.verifyDeployment(record);
    if (failures) {
      console.warn(
        `Verification incomplete (${failures} failure(s)). ` +
          `Re-run: NETWORK=${network.name} CONFIRM_SEPOLIA=yes make blockchain-verify`
      );
    }
  }

  console.log("");
  console.log("REMINDER: move DEFAULT_ADMIN_ROLE / ADMIN_ROLE / PAUSER_ROLE to a");
  console.log("multisig and grant MINTER/REWARDER/ROUTER to dedicated signers.");
  return record;
}

main()
  .then(() => process.exit(0))
  .catch((err) => {
    console.error(err);
    process.exit(1);
  });
