const lib = require("./_lib");

async function main() {
  const tokenId = BigInt(process.env.TOKEN_ID || "0");
  const opc = await lib.getDeployedContract();
  const supply = await opc["totalSupply(uint256)"](tokenId);
  console.log(`totalSupply [id=${tokenId}] = ${supply}`);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
