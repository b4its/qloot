const lib = require("./_lib");

async function main() {
  const tokenId = BigInt(process.env.TOKEN_ID || "0");
  const token = await lib.getDeployedContract();
  const supply = await token["totalSupply(uint256)"](tokenId);
  const capRaw = await token.maxSupplyOf(tokenId);
  const unlimited = capRaw >= (1n << 256n) - 1n;
  console.log(`totalSupply [id=${tokenId}] = ${supply} / cap ${unlimited ? "unlimited" : capRaw}`);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
