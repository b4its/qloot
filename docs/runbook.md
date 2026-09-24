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

## Background workers

| Worker | Compose service | Command | Responsibility |
|---|---|---|---|
| AI worker | `worker` | `python -m app.workers.main` | Drains AI grading + generation jobs, sweeps expired exam attempts (auto-submit) and auto-finalizes quests past `closes_at`. |
| Blockchain worker | `blockchain-worker` | `python -m app.workers.blockchain` | Submits outbox rows (rewards, withdrawals, swaps, anchors) on-chain. |
| Indexer | `indexer` | `python -m app.workers.indexer` | Resubmits stuck txs with a fee bump, rolls back reorged confirmations, ingests event logs, confirms txs. |
| Reconciler | `reconciler` | `python -m app.workers.reconciler` | Sweeps OPT accounts for cached-vs-ledger drift and repairs it. |

Each sweep is idempotent and uses `SKIP LOCKED`, so running multiple replicas is
safe. All workers use the simulation defaults offline (`AI_PROVIDER=mock`,
`BLOCKCHAIN_DRY_RUN=true`).


## Deploying the contract (Sepolia)

```bash
# Requires SEPOLIA_RPC_URL, BLOCKCHAIN_PRIVATE_KEY, ETHERSCAN_API_KEY, TREASURY_ADDRESS
make blockchain-build
make blockchain-deploy  NETWORK=sepolia CONFIRM_SEPOLIA=yes   # deploys OPT+QTC+ORT+ORX, auto-verifies
make blockchain-verify  NETWORK=sepolia CONFIRM_SEPOLIA=yes   # re-verify if needed
make blockchain-publish NETWORK=sepolia                       # public manifest (no secrets)
make blockchain-grant-role NETWORK=sepolia ASSET=OPT ROLE=REWARDER_ROLE ADDRESS=0x... CONFIRM_SEPOLIA=yes
make blockchain-status NETWORK=sepolia                        # show all 4 addresses + rates
```

Then set in `.env` (see `make blockchain-status` for the values):
`BLOCKCHAIN_DRY_RUN=false`, `OPT_CONTRACT_ADDRESS=0x...`,
`QTC_CONTRACT_ADDRESS=0x...`, `ORT_CONTRACT_ADDRESS=0x...`,
`ORX_CONTRACT_ADDRESS=0x...`, `BLOCKCHAIN_NETWORK=sepolia`, `CHAIN_ID=11155111`,
and restart the workers (the indexer must be able to reach the RPC).

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
Confirm the indexer is running (`make logs-blockchain`). The indexer resubmits a
transaction that is not mined past `TX_STUCK_SECONDS` with the same nonce and a
`TX_FEE_BUMP_PERCENT` higher fee (up to `TX_MAX_RESUBMITS`); after that it is
marked `dropped` and the ledger effect is compensated. If txs keep stalling,
check RPC health and raise `TX_PRIORITY_FEE_BUFFER`/`TX_BASE_FEE_BUFFER`.

**A confirmed transaction disappeared (reorg)**
The indexer revalidates recently-confirmed transactions against the canonical
chain. One whose receipt is no longer canonical is rolled back and compensated
(log `reorg_rollbacks`), and its event rows are cleared so a re-mine re-ingests
them. No manual action is normally needed; investigate if it recurs.

**Ledger mismatch**
`GET /api/v1/wallet/reconciliation` returns `cached_balance` vs `computed_balance`
for the caller. A mismatch means a bug: capture the account id and investigate
before crediting. The **reconciler worker** (`python -m app.workers.reconciler`,
compose service `reconciler`) sweeps every OPT account every 5 minutes: it detects
cached-vs-ledger drift, bumps `ledger_reconciliation_errors_total`, repairs the
cache to the ledger value, and logs `ledger_drift_detected`. Admins can trigger a
sweep on demand from `/admin/ledger` (or `POST /api/v1/admin/ledger/reconcile`)
and see accounts with a negative balance (`is_in_debt`) on the same page.

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
