# QLoot

**QLoot** is a gamified learning platform that combines digital learning, AI-assisted
exams and quests, competitive real-time rooms, rankings, and blockchain-based rewards
via the **OryphemCoin (OPC)** ERC-1155 token.

It is a ground-up reimplementation inspired by the domain of
[SayGenFix](https://github.com/mhaatha/saygenfix) (a Go/AI essay-exam app), rebuilt as
a FastAPI + SvelteKit monorepo with proper testing, transactions, and Web3 rewards.

---

## Highlights

- **Learning**: courses, lessons, progress tracking, PDF material upload.
- **AI**: question generation from PDFs and essay grading — with structured output,
  validation, retries and a mock provider for offline dev.
- **Exams**: server-authoritative timer, autosave, idempotent submit, AI feedback,
  similarity scores.
- **Gamification**: rooms (WebSocket live presence/leaderboard), quests with
  deterministic fastest-valid winner selection, tasks, global/room/quest rankings.
- **Web3 rewards**: shared treasury + **double-entry ledger**, idempotent reward keys,
  transactional outbox → blockchain worker → indexer, Etherscan links, withdrawals.
- **Security**: Argon2id, hashed sessions with expiry/revocation, object-level RBAC,
  CSRF-safe cookies, strict CORS, rate limiting, secret redaction in logs.

## Architecture

```
Browser → SvelteKit → FastAPI ─┬─ PostgreSQL
                               ├─ Redis (queue, pub/sub, rate limit)
                               ├─ MinIO / local storage (materials)
                               └─ Workers: ai, blockchain, indexer
                                        └─ ERC-1155 OryphemCoin (Hardhat)
```

See [`docs/architecture.md`](docs/architecture.md) for the full picture.

## Quick start

```bash
# 0. Prerequisites: Docker + Compose, Node 20+, Python 3.11+
cp .env.example .env          # then edit secrets
make setup                    # installs backend + frontend + contract deps
make up                       # postgres, redis, minio, backend, workers, frontend
make db-migrate               # apply Alembic migrations
make db-seed                  # demo admin/teacher/students + a course

# Open:
#  frontend  http://localhost:3000
#  api docs  http://localhost:8000/docs
#  minio     http://localhost:9001
```

Demo accounts (from `make db-seed`): `admin@qloot.example`, `teacher@qloot.example`,
`student1@qloot.example` (passwords in `apps/backend/app/db/seed.py`).

## Local blockchain

```bash
make blockchain-up            # Anvil on :8545 (chain 31337)
make blockchain-build         # compile contracts
make blockchain-test          # 23 contract tests
make blockchain-deploy NETWORK=localhost
make blockchain-show-all NETWORK=localhost
```

Sepolia deployment is guarded:

```bash
make blockchain-deploy NETWORK=sepolia CONFIRM_SEPOLIA=yes
make blockchain-verify  NETWORK=sepolia
make blockchain-publish NETWORK=sepolia
```

## Testing

```bash
make test-unit         # backend (needs PostgreSQL)
make test-contracts    # Hardhat
make test-frontend     # Vitest
make ci                # lint + typecheck + backend tests + contract tests
```

## Repository layout

```
apps/backend     FastAPI + SQLAlchemy async + Alembic + workers
apps/frontend    SvelteKit + TypeScript + Tailwind
blockchain       Hardhat + OpenZeppelin ERC-1155 (OryphemCoin)
infrastructure   proxy (Traefik/Nginx), monitoring (Prometheus/Grafana/Loki)
docs             architecture, api, blockchain, security, runbook
compose.yaml     development stack
compose.production.yaml  production overlay
Makefile         developer & ops entrypoint (run `make help`)
```

## Security

> **Never commit secrets.** All credentials are read from the environment. See
> [`docs/security.md`](docs/security.md). If a private key, RPC URL or API key was
> ever committed, treat it as compromised and rotate it immediately.

## License

MIT
