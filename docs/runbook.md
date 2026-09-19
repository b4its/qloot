# QLoot Runbook

## First-time setup

```bash
cp .env.example .env
# Edit .env: set POSTGRES_PASSWORD, SESSION_SECRET, and (for prod) chain/keys.
python - <<'PY'
import secrets; print("SESSION_SECRET=" + secrets.token_urlsafe(64))
PY
make setup          # backend + frontend + contract deps
make check-env      # verifies required vars
make up
make db-migrate
make db-seed
```

## Everyday development

```bash
make logs-backend        # tail a service
make dev-backend         # local uvicorn --reload
make dev-frontend        # local vite dev
make db-revision NAME=add_x && make db-upgrade
make test-unit && make test-contracts && make test-frontend
```

## Deploying the contract (Sepolia)

```bash
# Requires SEPOLIA_RPC_URL, BLOCKCHAIN_PRIVATE_KEY, ETHERSCAN_API_KEY, TREASURY_ADDRESS
make blockchain-build
make blockchain-deploy  NETWORK=sepolia CONFIRM_SEPOLIA=yes
make blockchain-verify  NETWORK=sepolia
make blockchain-publish NETWORK=sepolia      # public manifest (no secrets)
make blockchain-grant-role NETWORK=sepolia ROLE=REWARDER_ROLE ADDRESS=0x... CONFIRM_SEPOLIA=yes
```

Then set in `.env`: `BLOCKCHAIN_DRY_RUN=false`, `OPC_CONTRACT_ADDRESS=0x...`,
`BLOCKCHAIN_NETWORK=sepolia`, `CHAIN_ID=11155111`, and restart the workers.

After verifying, **transfer `DEFAULT_ADMIN_ROLE` / `PAUSER_ROLE` /
`URI_MANAGER_ROLE` to a multisig and revoke them from the deployer EOA.**

## Operating rewards

```bash
# Monitor
curl -s localhost:8000/api/v1/blockchain/status | jq
curl -s localhost:8000/api/v1/blockchain/transactions | jq

# A failed reward transaction (admin)
curl -XPOST localhost:8000/api/v1/admin/rewards/<id>/retry
curl -XPOST localhost:8000/api/v1/admin/rewards/<id>/cancel

# Emergency stop of on-chain transfers
curl -XPOST localhost:8000/api/v1/admin/blockchain/pause
curl -XPOST localhost:8000/api/v1/admin/blockchain/unpause
```

## Incidents

**Reward appears credited but has no on-chain tx**
Check `transaction_outbox` for the row; the blockchain worker may be down.
`make logs-blockchain` and retry via the admin endpoint.

**Transaction stuck `pending`**
Confirm the indexer is running (`make logs-blockchain`). Increase
`OPC_CONFIRMATIONS` or check RPC health.

**Ledger mismatch**
`GET /api/v1/wallet/reconciliation` returns `cached_balance` vs `computed_balance`.
A mismatch means a bug: capture the account id and investigate before crediting.

**Suspect a leaked key**
Rotate immediately (new wallet, new RPC key, new Etherscan key), move assets, and
follow `docs/security.md`.

## Backup / restore

```bash
make db-backup FILE=backup-$(date +%F).sql
make db-restore FILE=backup-2025-01-01.sql
```

## Production

```bash
make prod-up            # compose + production overlay
make migrate-prod
make monitoring-up      # prometheus (9090), grafana (3001), loki (3100)
```

Postgres/Redis/MinIO stay on internal networks and are never publicly exposed.
