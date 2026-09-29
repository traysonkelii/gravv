.DEFAULT_GOAL := help
SHELL := /bin/bash

help: ## list targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "%-14s %s\n", $$1, $$2}'

setup: ## first-time setup
	cd apps/api && uv sync
	cd apps/web && pnpm install
	uv tool install pre-commit >/dev/null 2>&1 || true
	pre-commit install >/dev/null 2>&1 || true
	supabase start
	scripts/env.sh
	$(MAKE) db-reset
	$(MAKE) gen

dev: ## run everything locally
	scripts/dev.sh

env: ## write .env from the running local stack
	scripts/env.sh

db-reset: ## rebuild the local database from migrations and seed
	supabase db reset
	infra/scripts/setup_roles.sh local
	$(MAKE) seed

db-migrate: ## make db-migrate name=<change>
	supabase migration new $(name)

db-diff: ## fail if the live schema drifted from migrations
	@diff=$$(supabase db diff --local --output-format json 2>/dev/null | jq -r '.diff // empty'); \
	if [[ -n "$$diff" ]]; then echo "$$diff"; echo "schema drift detected"; exit 1; else echo "no schema drift"; fi

seed: ## create seed users through the auth admin API and load supabase/seed.sql
	cd apps/api && uv run python -m scripts.seed_users

gen: ## regenerate the TypeScript API client
	cd apps/api && APP_ENV=test uv run python -m scripts.export_openapi > ../web/src/lib/api/openapi.json
	cd apps/web && pnpm exec openapi-typescript src/lib/api/openapi.json -o src/lib/api/schema.d.ts && pnpm exec prettier --write src/lib/api/schema.d.ts src/lib/api/openapi.json >/dev/null

lint: ## all linters
	cd apps/api && uv run ruff check . && uv run ruff format --check . && uv run mypy .
	cd apps/web && pnpm lint && pnpm exec prettier --check . && pnpm exec tsc --noEmit && pnpm design-lint

format: ## auto-format both apps
	cd apps/api && uv run ruff check --fix . && uv run ruff format .
	cd apps/web && pnpm exec prettier --write . >/dev/null

test: ## unit + integration tests
	cd apps/api && uv run pytest -q
	cd apps/web && pnpm test -- --run

test-e2e: ## playwright against the local stack
	cd apps/web && pnpm exec playwright test

ai-eval: ## run the AI extraction eval cases against the configured provider
	cd apps/api && uv run python -m scripts.ai_eval

check: lint test db-diff ## the milestone gate

build: ## container image and static bundle
	docker build -t gravv-api:local apps/api
	cd apps/web && pnpm build

jobs-requeue: ## make jobs-requeue id=<job id>
	cd apps/api && uv run python -m scripts.requeue_job $(id)

.PHONY: help setup dev env db-reset db-migrate db-diff seed gen lint format test test-e2e ai-eval check build jobs-requeue
