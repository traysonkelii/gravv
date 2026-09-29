#!/usr/bin/env bash
# Starts the API and the worker together for Playwright's webServer (it can only wait on one URL).
set -euo pipefail
cd "$(dirname "$0")/../apps/api"
trap 'kill 0' EXIT INT TERM
uv run python -m app.worker &
exec uv run uvicorn app.main:app --port 8000
