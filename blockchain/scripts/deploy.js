// Deploy OryphemCoin1155.
//
// Secret handling: the deployer key is read from BLOCKCHAIN_PRIVATE_KEY via the
// hardhat network config. It is never accepted as a CLI argument.
//
//   NETWORK=localhost make blockchain-deploy
//   NETWORK=sepolia CONFIRM_SEPOLIA=yes make blockchain-deploy
const { ethers, network } = require("hardhat");
const lib = require("./_lib");

const OPC_NAME = process.env.OPC_NAME || "OryphemCoin";
const OPC_SYMBOL = process.env.OPC_SYMBOL || "OPC";
const OPC_URI =
  process.env.OPC_URI || "https://metadata.qloot.example/opc/{id}.json";

async function main() {
  const [deployer] = await ethers.getSigners();
  const net = await ethers.provider.getNetwork();
  const chainId = Number(net.chainId);

  const admin = process.env.OPC_ADMIN_ADDRESS || deployer.address;
  const treasury = process.env.TREASURY_ADDRESS || deployer.address;

  console.log("----------------------------------------");
  console.log(`Network     : ${network.name} (chainId=${chainId})`);
  console.log(`Deployer    : ${deployer.address}`);
  console.log(`Admin       : ${admin}`);
  console.log(`Treasury    : ${treasury}`);
  console.log(`URI         : ${OPC_URI}`);
  console.log("----------------------------------------");

  const Factory = await ethers.getContractFactory(lib.CONTRACT_NAME);
  const opc = await Factory.deploy(OPC_NAME, OPC_SYMBOL, OPC_URI, admin);
  await opc.waitForDeployment();

  const address = await opc.getAddress();
  const tx = opc.deploymentTransaction();
  const receipt = await tx.wait();

  const record = {
    contractName: lib.CONTRACT_NAME,
    name: OPC_NAME,
    symbol: OPC_SYMBOL,
    uri: OPC_URI,
    address,
    deployer: deployer.address,
    admin,
    treasury,
    tokenId: 0,
    chainId,
    network: network.name,
    txHash: tx.hash,
    blockNumber: receipt ? receipt.blockNumber : null,
    deployedAt: new Date().toISOString(),
  };

  lib.writeDeployment(record, network.name);
  const pub = lib.writePublicManifest(record, network.name);

  const explorer = lib.explorerUrl(chainId, tx.hash);
  console.log(`OPC deployed to: ${address}`);
  console.log(`tx: ${tx.hash}`);
  if (explorer) console.log(`explorer: ${explorer}`);
  console.log(`manifest: deployments/${network.name}.json`);
  console.log(`public  : deployments/${network.name}.public.json`);
  console.log("");
  console.log(
    "REMINDER: move DEFAULT_ADMIN_ROLE / PAUSER_ROLE / URI_MANAGER_ROLE to a"
  );
  console.log("multisig and grant MINTER/REWARDER to a dedicated backend signer.");
  return address;
}

main()
  .then((a) => process.exit(0))
  .catch((err) => {
    console.error(err);
    process.exit(1);
  });
