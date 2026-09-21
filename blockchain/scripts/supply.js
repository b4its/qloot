// Show the total supply (and cap) of a QLoot asset.
//   ASSET=OPT make blockchain-supply        # OPT (unlimited)
//   ASSET=QTC make blockchain-supply        # QTC (cap 1e15)
const lib = require("./_lib");

async function main() {
  const key = (process.env.ASSET || "OPT").toUpperCase();
  if (!lib.CONTRACTS[key] || key === "ORX") {
    throw new Error("ASSET must be one of OPT, QTC, ORT");
  }
  const token = await lib.attach(key);
  const supply = await token["totalSupply(uint256)"](0);
  const cap = await token.maxSupply();
  console.log(`${key} totalSupply = ${supply} / cap ${cap === 0n ? "unlimited" : cap}`);
}

main().catch((e) => {
  console.error(e.message || e);
  process.exit(1);
});
