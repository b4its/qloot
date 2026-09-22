#!/usr/bin/env bash
# Verify required environment variables are present and non-placeholder.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${1:-$ROOT/.env}"

err=0
warn=0

if [[ ! -f "$ENV_FILE" ]]; then
  echo "ERROR: env file not found: $ENV_FILE (copy .env.example to .env)"
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

require() {
  local name="$1"
  local val="${!name:-}"
  if [[ -z "$val" ]]; then
    echo "ERROR: $name is not set"
    err=1
  elif [[ "$val" == *"change-me"* || "$val" == *"replace-me"* ]]; then
    echo "WARN:  $name still has a placeholder value"
    warn=1
  fi
}

require POSTGRES_DB
require POSTGRES_USER
require POSTGRES_PASSWORD
require DATABASE_URL
require REDIS_URL
require SESSION_SECRET
require CORS_ORIGINS

# Blockchain vars warn only unless network is a real chain.
BLOCKCHAIN_NETWORK="${BLOCKCHAIN_NETWORK:-localhost}"
if [[ "$BLOCKCHAIN_NETWORK" != "localhost" && "$BLOCKCHAIN_NETWORK" != "anvil" ]]; then
  require SEPOLIA_RPC_URL
  require BLOCKCHAIN_PRIVATE_KEY
  require TREASURY_ADDRESS
  # QLoot ships 4 separate asset contracts; OPT may fall back to the legacy
  # OPC_CONTRACT_ADDRESS alias, but QTC/ORT/ORX must be set for live routing.
  if [[ -z "${OPT_CONTRACT_ADDRESS:-}" && -z "${OPC_CONTRACT_ADDRESS:-}" ]]; then
    echo "ERROR: OPT_CONTRACT_ADDRESS (or OPC_CONTRACT_ADDRESS) is not set"
    err=1
  fi
  require QTC_CONTRACT_ADDRESS
  require ORT_CONTRACT_ADDRESS
  require ORX_CONTRACT_ADDRESS
fi

if [[ "$err" -ne 0 ]]; then
  echo ""
  echo "Environment check FAILED."
  exit 1
fi

echo "Environment check passed${warn:+ (with warnings)}."
