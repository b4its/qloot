# ============================================================================
# QLoot — developer & operations entrypoint
# Run `make help` for the full target list.
# ============================================================================

SHELL := /bin/bash
.DEFAULT_GOAL := help

COMPOSE ?= docker compose
COMPOSE_FILE ?= compose.yaml
COMPOSE_PROD_FILE ?= compose.production.yaml
BACKEND_SVC ?= backend
FRONTEND_SVC ?= frontend
DB_SVC ?= postgres
REDIS_SVC ?= redis

NETWORK ?= localhost
CONFIRM_SEPOLIA ?= no

# Chain deploy params (override on the command line, e.g. TO=0x.. AMOUNT=100)
TO ?=
FROM ?=
AMOUNT ?=
ADDRESS ?=
ROLE ?=
TOKEN_ID ?= 0

COMPOSE_DEV = $(COMPOSE) -f $(COMPOSE_FILE)
COMPOSE_PROD = $(COMPOSE) -f $(COMPOSE_FILE) -f $(COMPOSE_PROD_FILE)

# ANSI
BOLD := \033[1m
DIM := \033[2m
GREEN := \033[32m
YELLOW := \033[33m
RED := \033[31m
RESET := \033[0m

.PHONY: help
help: ## Show this help
	@printf "\n"
	@printf "  $(BOLD)QLoot$(RESET) — gamified learning on Web3 + AI\n"
	@printf "  $(DIM)Usage: make <target> [VAR=value]$(RESET)\n\n"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z0-9_.-]+:.*?## / {printf "  $(GREEN)%-26s$(RESET) %s\n", $$1, $$2}' $(MAKEFILE_LIST) | sort
	@printf "\n"

# ----------------------------------------------------------------------------
# General
# ----------------------------------------------------------------------------
.PHONY: setup
setup: ## First-time setup: copy .env, install deps, compile contracts
	@[ -f .env ] || (cp .env.example .env && echo "$(YELLOW)Created .env from .env.example — review it!$(RESET)")
	$(MAKE) install
	$(MAKE) blockchain-install

.PHONY: check-env
check-env: ## Verify required env vars are set
	@bash scripts/check-env.sh

.PHONY: install
install: ## Install backend + frontend dependencies
	@echo ">> backend deps"; (cd apps/backend && python3 -m venv .venv && .venv/bin/pip install -q -U pip && .venv/bin/pip install -q -e ".[dev]")
	@echo ">> frontend deps"; (cd apps/frontend && npm install --no-fund --no-audit)

.PHONY: build
build: ## Build all container images
	$(COMPOSE_DEV) build

.PHONY: clean
clean: ## Remove build artifacts and caches
	rm -rf apps/frontend/.svelte-kit apps/frontend/build
	rm -rf apps/backend/.venv apps/backend/.pytest_cache apps/backend/.ruff_cache
	find . -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true
	rm -rf blockchain/artifacts blockchain/cache blockchain/typechain-types

.PHONY: status
status: ## Show container status
	$(COMPOSE_DEV) ps

.PHONY: health
health: ## Hit health endpoints
	@curl -fsS http://localhost:8000/api/v1/health/live && echo " <- backend live"
	@curl -fsS http://localhost:8000/api/v1/health/ready && echo " <- backend ready"
	@curl -fsSI http://localhost:3000 >/dev/null && echo "frontend up"

# ----------------------------------------------------------------------------
# Containers
# ----------------------------------------------------------------------------
.PHONY: up
up: ## Start the core stack (detached)
	$(COMPOSE_DEV) up -d --remove-orphans
	@echo ">> backend:  http://localhost:8000/docs"
	@echo ">> frontend: http://localhost:3000"

.PHONY: up-all
up-all: ## Start core stack + local anvil chain
	$(COMPOSE_DEV) --profile local-chain up -d --remove-orphans

.PHONY: down
down: ## Stop the stack
	$(COMPOSE_DEV) down

.PHONY: down-v
down-v: ## Stop the stack and delete volumes (DESTRUCTIVE)
	$(COMPOSE_DEV) down -v

.PHONY: restart
restart: ## Restart the stack
	$(COMPOSE_DEV) restart

.PHONY: rebuild
rebuild: ## Rebuild images and restart
	$(COMPOSE_DEV) build && $(COMPOSE_DEV) up -d --remove-orphans

.PHONY: ps
ps: ## List containers
	$(COMPOSE_DEV) ps

.PHONY: logs
logs: ## Tail all logs
	$(COMPOSE_DEV) logs -f --tail=100

.PHONY: logs-backend
logs-backend: ## Tail backend logs
	$(COMPOSE_DEV) logs -f --tail=200 $(BACKEND_SVC)

.PHONY: logs-frontend
logs-frontend: ## Tail frontend logs
	$(COMPOSE_DEV) logs -f --tail=200 $(FRONTEND_SVC)

.PHONY: logs-worker
logs-worker: ## Tail worker logs
	$(COMPOSE_DEV) logs -f --tail=200 worker blockchain-worker blockchain-indexer

.PHONY: logs-blockchain
logs-blockchain: ## Tail blockchain worker + indexer logs
	$(COMPOSE_DEV) logs -f --tail=200 blockchain-worker blockchain-indexer

.PHONY: pull
pull: ## Pull latest images
	$(COMPOSE_DEV) pull

.PHONY: prune
prune: ## Prune docker build cache
	docker builder prune -f

# ----------------------------------------------------------------------------
# Development
# ----------------------------------------------------------------------------
.PHONY: dev
dev: up ## Alias for up

.PHONY: dev-backend
dev-backend: ## Run backend with autoreload (local, no docker)
	cd apps/backend && .venv/bin/uvicorn app.main:app --reload --port 8000

.PHONY: dev-frontend
dev-frontend: ## Run frontend dev server (local)
	cd apps/frontend && npm run dev

.PHONY: dev-worker
dev-worker: ## Run the task worker (local)
	cd apps/backend && .venv/bin/python -m app.workers.main

.PHONY: shell-backend
shell-backend: ## Shell into backend container
	$(COMPOSE_DEV) exec $(BACKEND_SVC) bash

.PHONY: shell-frontend
shell-frontend: ## Shell into frontend container
	$(COMPOSE_DEV) exec $(FRONTEND_SVC) sh

.PHONY: shell-db
shell-db: ## psql into postgres
	$(COMPOSE_DEV) exec $(DB_SVC) psql -U $${POSTGRES_USER:-qloot} -d $${POSTGRES_DB:-qloot}

.PHONY: shell-redis
shell-redis: ## redis-cli into redis
	$(COMPOSE_DEV) exec $(REDIS_SVC) redis-cli

# ----------------------------------------------------------------------------
# Quality
# ----------------------------------------------------------------------------
.PHONY: format
format: ## Format backend (ruff), frontend (prettier), contracts (prettier-plugin)
	cd apps/backend && .venv/bin/ruff format app tests
	cd apps/frontend && npm run format || true
	cd blockchain && npm run format || true

.PHONY: lint
lint: ## Lint backend + frontend + contracts
	cd apps/backend && .venv/bin/ruff check app tests
	cd apps/frontend && npm run lint || true
	cd blockchain && npm run lint || true

.PHONY: typecheck
typecheck: ## Typecheck backend (mypy) + frontend (svelte-check)
	cd apps/backend && .venv/bin/mypy app
	cd apps/frontend && npm run check

.PHONY: test
test: test-unit ## Alias for test-unit

.PHONY: test-unit
test-unit: ## Backend unit tests
	cd apps/backend && .venv/bin/pytest -q -m "not integration"

.PHONY: test-integration
test-integration: ## Backend integration tests (needs postgres)
	cd apps/backend && .venv/bin/pytest -q -m integration

.PHONY: test-contracts
test-contracts: ## Hardhat contract tests
	cd blockchain && npx hardhat test

.PHONY: test-frontend
test-frontend: ## Frontend unit tests
	cd apps/frontend && npm run test -- --run

.PHONY: test-e2e
test-e2e: ## End-to-end tests (needs full stack)
	cd apps/frontend && npm run test:e2e

.PHONY: backend-test
backend-test: test-unit ## Backend tests (alias)

.PHONY: coverage
coverage: ## Backend coverage report
	cd apps/backend && .venv/bin/pytest --cov=app --cov-report=term-missing --cov-report=html

.PHONY: security
security: ## Security scans (bandit, npm audit, hardhat compile)
	cd apps/backend && .venv/bin/bandit -q -r app || true
	cd apps/frontend && npm audit --audit-level=high || true

.PHONY: ci
ci: lint typecheck test-unit test-contracts ## Full CI pipeline

# ----------------------------------------------------------------------------
# Database
# ----------------------------------------------------------------------------
.PHONY: db-up
db-up: ## Start postgres
	$(COMPOSE_DEV) up -d $(DB_SVC)

.PHONY: db-down
db-down: ## Stop postgres
	$(COMPOSE_DEV) stop $(DB_SVC)

.PHONY: db-migrate
db-migrate: ## Apply migrations (in container)
	$(COMPOSE_DEV) run --rm migrate

.PHONY: db-revision
db-revision: ## New revision: make db-revision NAME=add_x
	cd apps/backend && .venv/bin/alembic revision --autogenerate -m "$(NAME)"

.PHONY: db-upgrade
db-upgrade: ## alembic upgrade head (local)
	cd apps/backend && .venv/bin/alembic upgrade head

.PHONY: db-downgrade
db-downgrade: ## alembic downgrade -1 (local)
	cd apps/backend && .venv/bin/alembic downgrade -1

.PHONY: db-current
db-current: ## Show current revision
	cd apps/backend && .venv/bin/alembic current

.PHONY: db-history
db-history: ## Show migration history
	cd apps/backend && .venv/bin/alembic history

.PHONY: db-reset
db-reset: ## Drop + recreate schema + migrate (DESTRUCTIVE, dev only)
	$(COMPOSE_DEV) exec -T $(DB_SVC) psql -U $${POSTGRES_USER:-qloot} -d $${POSTGRES_DB:-qloot} -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
	$(MAKE) db-upgrade
	$(MAKE) db-seed

.PHONY: db-seed
db-seed: ## Seed demo data
	cd apps/backend && .venv/bin/python -m app.db.seed

.PHONY: db-backup
db-backup: ## Backup database to FILE=backup.sql
	$(COMPOSE_DEV) exec -T $(DB_SVC) pg_dump -U $${POSTGRES_USER:-qloot} $${POSTGRES_DB:-qloot} > $(FILE)

.PHONY: db-restore
db-restore: ## Restore database from FILE=backup.sql
	cat $(FILE) | $(COMPOSE_DEV) exec -T $(DB_SVC) psql -U $${POSTGRES_USER:-qloot} -d $${POSTGRES_DB:-qloot}

# ----------------------------------------------------------------------------
# Blockchain (Hardhat)
# ----------------------------------------------------------------------------
.PHONY: blockchain-install
blockchain-install: ## Install contract deps
	cd blockchain && npm install --no-fund --no-audit

.PHONY: blockchain-build
blockchain-build: ## Compile contracts
	cd blockchain && npx hardhat compile

.PHONY: blockchain-test
blockchain-test: ## Run contract tests
	cd blockchain && npx hardhat test

.PHONY: blockchain-coverage
blockchain-coverage: ## Contract coverage
	cd blockchain && npx hardhat coverage

.PHONY: blockchain-format
blockchain-format: ## Format solidity + js
	cd blockchain && npx prettier --write "**/*.{sol,js,json}" --ignore-path .prettierignore || true

.PHONY: blockchain-lint
blockchain-lint: ## Solhint
	cd blockchain && npx solhint "contracts/**/*.sol" || true

.PHONY: blockchain-up
blockchain-up: ## Start local Anvil chain
	$(COMPOSE_DEV) --profile local-chain up -d anvil
	@echo ">> anvil rpc http://localhost:8545 (chain 31337)"

.PHONY: blockchain-down
blockchain-down: ## Stop local Anvil
	$(COMPOSE_DEV) --profile local-chain stop anvil

.PHONY: blockchain-restart
blockchain-restart: ## Restart Anvil
	$(MAKE) blockchain-down && $(MAKE) blockchain-up

.PHONY: blockchain-logs
blockchain-logs: ## Tail Anvil logs
	$(COMPOSE_DEV) logs -f --tail=100 anvil

.PHONY: _require-sepolia
_require-sepolia:
	@if [ "$(NETWORK)" = "sepolia" ] && [ "$(CONFIRM_SEPOLIA)" != "yes" ]; then \
		echo "$(RED)Refusing: set CONFIRM_SEPOLIA=yes to act on Sepolia$(RESET)"; exit 1; fi

.PHONY: blockchain-deploy
blockchain-deploy: _require-sepolia ## Deploy OryphemCoin: NETWORK=localhost|sepolia
	cd blockchain && npx hardhat run scripts/deploy.js --network $(NETWORK)

.PHONY: blockchain-verify
blockchain-verify: _require-sepolia ## Verify source on Etherscan: NETWORK=sepolia
	cd blockchain && npx hardhat run scripts/verify.js --network $(NETWORK)

.PHONY: blockchain-publish
blockchain-publish: ## Publish metadata + deployment manifest
	cd blockchain && npx hardhat run scripts/publish-metadata.js --network $(NETWORK)

.PHONY: blockchain-mint
blockchain-mint: _require-sepolia ## Mint OPC: TO=0x.. AMOUNT=100 [TOKEN_ID=0]
	cd blockchain && TO=$(TO) AMOUNT=$(AMOUNT) TOKEN_ID=$(TOKEN_ID) npx hardhat run scripts/mint.js --network $(NETWORK)

.PHONY: blockchain-transfer
blockchain-transfer: _require-sepolia ## Transfer OPC: TO=0x.. AMOUNT=10
	cd blockchain && TO=$(TO) AMOUNT=$(AMOUNT) TOKEN_ID=$(TOKEN_ID) npx hardhat run scripts/transfer.js --network $(NETWORK)

.PHONY: blockchain-balance
blockchain-balance: ## Show balance: ADDRESS=0x..
	cd blockchain && ADDRESS=$(ADDRESS) TOKEN_ID=$(TOKEN_ID) npx hardhat run scripts/balance.js --network $(NETWORK)

.PHONY: blockchain-supply
blockchain-supply: ## Show total supply of token id
	cd blockchain && TOKEN_ID=$(TOKEN_ID) npx hardhat run scripts/supply.js --network $(NETWORK)

.PHONY: blockchain-events
blockchain-events: ## Dump recent contract events
	cd blockchain && npx hardhat run scripts/events.js --network $(NETWORK)

.PHONY: blockchain-status
blockchain-status: ## Show network + contract + treasury summary
	cd blockchain && npx hardhat run scripts/status.js --network $(NETWORK)

.PHONY: blockchain-show-all
blockchain-show-all: ## Print full on-chain summary (network, supply, balances, roles)
	cd blockchain && npx hardhat run scripts/show-all.js --network $(NETWORK)

.PHONY: blockchain-pause
blockchain-pause: _require-sepolia ## Pause token transfers
	cd blockchain && npx hardhat run scripts/pause.js --network $(NETWORK)

.PHONY: blockchain-unpause
blockchain-unpause: _require-sepolia ## Unpause token transfers
	cd blockchain && npx hardhat run scripts/unpause.js --network $(NETWORK)

.PHONY: blockchain-grant-role
blockchain-grant-role: _require-sepolia ## Grant role: ROLE=MINTER_ROLE ADDRESS=0x..
	cd blockchain && ROLE=$(ROLE) ADDRESS=$(ADDRESS) npx hardhat run scripts/grant-role.js --network $(NETWORK)

.PHONY: blockchain-revoke-role
blockchain-revoke-role: _require-sepolia ## Revoke role: ROLE=MINTER_ROLE ADDRESS=0x..
	cd blockchain && ROLE=$(ROLE) ADDRESS=$(ADDRESS) npx hardhat run scripts/revoke-role.js --network $(NETWORK)

# ----------------------------------------------------------------------------
# Production / observability
# ----------------------------------------------------------------------------
.PHONY: prod-up
prod-up: ## Start production stack
	$(COMPOSE_PROD) up -d --remove-orphans

.PHONY: prod-down
prod-down: ## Stop production stack
	$(COMPOSE_PROD) down

.PHONY: migrate-prod
migrate-prod: ## Run production migrations
	$(COMPOSE_PROD) run --rm migrate

.PHONY: monitoring-up
monitoring-up: ## Start prometheus + grafana + loki
	$(COMPOSE_DEV) --profile monitoring up -d

.PHONY: monitoring-down
monitoring-down: ## Stop monitoring
	$(COMPOSE_DEV) --profile monitoring stop prometheus grafana loki
