#!/usr/bin/env bash
# Runs api, worker, and web in one terminal. Ctrl-C stops all three.
set -euo pipefail
cd "$(dirname "$0")/.."
supabase start >/dev/null 2>&1 || true
[[ -f .env ]] || scripts/env.sh
trap 'kill 0' EXIT INT TERM
(cd apps/api && uv run uvicorn app.main:app --reload --port 8000 2>&1 | sed -u 's/^/[api]    /') &
(cd apps/api && uv run python -m app.worker 2>&1 | sed -u 's/^/[worker] /') &
(cd apps/web && pnpm dev 2>&1 | sed -u 's/^/[web]    /') &
wait
