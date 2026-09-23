# QLoot Architecture

## Services

| Service | Purpose |
|---|---|
| `frontend` | SvelteKit (adapter-node) UI |
| `backend` | FastAPI REST + WebSocket API |
| `worker` | AI generation & grading jobs, expired-attempt sweeper |
| `blockchain-worker` | Signs & submits on-chain transactions (outbox drainer) |
| `blockchain-indexer` | Tracks confirmations, promotes rewards to `confirmed` |
| `reconciler` | Sweeps OPT accounts for cached-vs-ledger drift and repairs it |
| `postgres` | Primary datastore |
| `redis` | Queue, cache, rate-limit, pub/sub for live rooms |
| `minio` | Object storage for PDFs (local dev) |
| `migrate` | One-shot Alembic migration |
| `anvil` | Local EVM chain (dev, profile `local-chain`) |
| `blockchain-toolbox` | Hardhat tooling container (profile `blockchain-tools`) |
| `reverse-proxy` | Traefik (profile `proxy`) |

## Networks

- `public-network` — browser ↔ frontend
- `application-network` — frontend ↔ backend ↔ workers
- `data-network` — backend/workers ↔ postgres/redis/minio (internal; not exposed)
- `blockchain-network` — blockchain worker/indexer ↔ anvil/RPC

PostgreSQL, Redis and MinIO are **not** exposed publicly. The blockchain signer
(worker) is never reachable from the frontend.

## Backend layering

```
FastAPI Router (app/api/v1)
  → Service (app/services)
    → Repository (app/repositories) / SQLAlchemy models (app/models)
      → PostgreSQL
```

Cross-cutting: `app/core` (config, logging, security, errors, metrics),
`app/middleware` (request id, security headers), `app/ai` (providers),
`app/blockchain` (chain client + worker logic), `app/workers`.

## Transactions

`get_db` owns one request-scoped transaction: it commits once at the end of a
successful request and rolls back on any error. `transaction()` joins that
unit of work, or opens its own when used standalone (workers use
`session_scope()`). This fixes the SayGenFix bug where a deferred commit could
run even on error.

## Exam & grading flow

1. Teacher uploads a PDF → text extracted (pypdf) → stored.
2. AI generation job drafts questions (`review_status=pending`).
3. Teacher reviews/approves, attaches questions to an exam, publishes.
4. Student starts an attempt; answers autosave (idempotent upsert).
5. Submit stamps a server-authoritative `submitted_at`. Multiple-choice questions
   are graded deterministically; an MC-only exam is graded instantly at submit,
   while an exam with any essay question enqueues a grading job.
6. Worker scores the essays via the AI provider (call made **outside** any DB
   transaction), storing per-answer scores/feedback in integer basis points; the
   attempt gets an overall score (MC + essay / full exam max).

## Reward flow (the §11.3 model)
```
quest.finalize()
  → select winners (deterministic)         ┐ single DB transaction
  → reward_allocation (idempotent key)     │
  → ledger credit (double-entry)           │
  → transaction_outbox row                 ┘
        ↓ (blockchain-worker)
  → BlockchainTransaction (sign → send → hash)
        ↓ (indexer)
  → confirmations → reward status = confirmed
```

**Winner ordering** (server-authoritative, not request-completion order):
quest open → valid attempt before deadline → score ≥ min passing → not flagged →
order by `submitted_at`, then higher score, then shorter duration, then lower
attempt id.

## Wallet model

On-chain: the treasury holds the pooled assets (OPT/QTC/ORT). Off-chain: a
**double-entry ledger** (`credit − debit = balance`) tracks each user's
beneficial balance, with cached balances for fast reads and a reconciliation
endpoint. Rewards are idempotent at both the database (`reward_key` unique,
`(quest,user,type)` unique) and contract (`rewardKeyUsed` mapping) layers. Users
may withdraw to a personal address; the OryphemProxy (ORX) router converts OPT
into QTC/ORT at fixed rates.

## Observability

- Structured JSON logs (structlog) with `request_id`/`user_id` context and secret
  redaction.
- Prometheus metrics at `/api/v1/metrics` (requests, durations, ai jobs, rewards,
  blockchain transactions/failures).
- Grafana + Loki available under the `monitoring` profile.

## Career guidance module (simulated)

A self-contained, deterministic module adapted from an academic-path planner:

```
grades ─┐
        ├─► RecommendationEngine ─► recommendations ─► [counsellor approve] ─► roadmap
Big Five┘                                                        │
                                                     consultations / notifications
```

- **Determinism**: no external AI calls. The recommendation engine computes,
  for each major, a weighted academic score over subject grades and a
  personality score over Big Five traits (negative weights invert a trait, e.g.
  lower neuroticism is better).
- **Human-in-the-loop**: recommendations are `draft` → `in_review` →
  `approved`; the roadmap only generates on approval, mirroring the safety
  requirement that a human validates AI output.
- **Data**: `academic_grades`, `personality_results`, `career_recommendations`,
  `roadmap_milestones`, `consultations`, `resource_items`.
- **Assistant**: a rule-based keyword responder (also deterministic) that can be
  swapped for the real AI provider later.

Everything is seeded by `python -m app.db.seed`, so the UI is populated and
demonstrable without any external service.
