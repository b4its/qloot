require("@nomicfoundation/hardhat-toolbox");
require("@openzeppelin/hardhat-upgrades");
require("dotenv").config({ path: require("path").resolve(__dirname, "..", ".env") });

// The private key is only ever read from the environment. It is NEVER passed
// as a CLI argument and NEVER written to a file tracked by git.
const DEPLOYER_KEY = process.env.BLOCKCHAIN_PRIVATE_KEY || "";
const accounts = DEPLOYER_KEY ? [DEPLOYER_KEY] : [];

const SEPOLIA_RPC_URL = process.env.SEPOLIA_RPC_URL || "";
const LOCALHOST_RPC_URL = process.env.LOCALHOST_RPC_URL || "http://127.0.0.1:8545";
const ETHERSCAN_API_KEY = process.env.ETHERSCAN_API_KEY || "";

/** @type import('hardhat/config').HardhatUserConfig */
module.exports = {
  solidity: {
    version: "0.8.28",
    settings: {
      // `runs: 1` prioritises deployment size over runtime gas, which keeps the
      // feature-rich OPC contract under the 24 576-byte mainnet limit.
      optimizer: { enabled: true, runs: 1 },
      // OpenZeppelin 5.x uses the MCOPY opcode, which requires Cancun.
      evmVersion: "cancun",
      // recordRewards() needs the IR pipeline to avoid "stack too deep".
      viaIR: true,
    },
  },
  networks: {
    hardhat: {
      chainId: 31337,
    },
    localhost: {
      url: LOCALHOST_RPC_URL,
      chainId: 31337,
    },
    anvil: {
      url: LOCALHOST_RPC_URL,
      chainId: 31337,
    },
    sepolia: {
      url: SEPOLIA_RPC_URL,
      chainId: 11155111,
      accounts,
    },
  },
  etherscan: {
    // Etherscan API v2: a single (universal) key covers all chains. The old
    // per-network map relied on the deprecated v1 endpoints.
    apiKey: ETHERSCAN_API_KEY,
  },
  gasReporter: {
    enabled: process.env.REPORT_GAS === "true",
  },
  paths: {
    sources: "./contracts",
    tests: "./test",
    cache: "./cache",
    artifacts: "./artifacts",
  },
};
