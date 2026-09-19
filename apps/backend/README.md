# QLoot Backend

FastAPI service for QLoot — gamified learning with AI grading and Web3 rewards.

See the repository root `README.md` and `docs/` for the full architecture.

## Layout

```
app/
  api/v1/         HTTP routers
  core/           config, logging, security, errors
  db/             engine, session, transaction helpers, base
  models/         SQLAlchemy models (identity, learning, room, exam, quest, ranking, wallet)
  schemas/        Pydantic request/response models
  repositories/   data access
  services/       application logic
  ai/             AI provider abstraction (mock + gemini)
  blockchain/     web3 client, contract wrapper, ledger
  workers/        background workers (ai, blockchain, indexer)
migrations/       Alembic
tests/            pytest
```

## Run

```bash
cp ../../.env.example ../../.env
python -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/alembic upgrade head
.venv/bin/uvicorn app.main:app --reload
```

Or via Docker Compose from the repo root: `make up`.
