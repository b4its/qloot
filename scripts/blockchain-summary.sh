#!/usr/bin/env bash
# Show the local blockchain + contract summary via hardhat.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../blockchain"
NETWORK="${NETWORK:-localhost}"
exec npx hardhat run scripts/show-all.js --network "$NETWORK"
