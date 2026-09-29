#!/usr/bin/env bash
# Background dev servers with pid files: scripts/devctl.sh start|stop|status [api|worker|web ...]
set -uo pipefail
cd "$(dirname "$0")/.."
export PATH="$HOME/.local/bin:$PATH" COREPACK_ENABLE_DOWNLOAD_PROMPT=0
RUN_DIR="${DEVCTL_DIR:-/tmp/gravv-dev}"; mkdir -p "$RUN_DIR"
cmd="${1:-status}"; shift || true
targets=("$@"); [[ ${#targets[@]} -eq 0 ]] && targets=(api worker web)

start_one() {
  case "$1" in
    api)    (cd apps/api && nohup uv run uvicorn app.main:app --port 8000 > "$RUN_DIR/api.log" 2>&1 & echo $! > "$RUN_DIR/api.pid") ;;
    worker) (cd apps/api && nohup uv run python -m app.worker > "$RUN_DIR/worker.log" 2>&1 & echo $! > "$RUN_DIR/worker.pid") ;;
    web)    (cd apps/web && nohup pnpm dev > "$RUN_DIR/web.log" 2>&1 & echo $! > "$RUN_DIR/web.pid") ;;
  esac
}
stop_one() {
  local f="$RUN_DIR/$1.pid"
  if [[ -f "$f" ]]; then
    local pid; pid=$(cat "$f")
    # kill the whole process tree (uv run / pnpm spawn children)
    pkill -TERM -P "$pid" 2>/dev/null; kill -TERM "$pid" 2>/dev/null
    for _ in 1 2 3 4 5; do kill -0 "$pid" 2>/dev/null || break; timeout 1 tail -f /dev/null; done
    pkill -KILL -P "$pid" 2>/dev/null; kill -KILL "$pid" 2>/dev/null
    rm -f "$f"
  fi
}
case "$cmd" in
  start)  for t in "${targets[@]}"; do stop_one "$t"; start_one "$t"; done ;;
  stop)   for t in "${targets[@]}"; do stop_one "$t"; done ;;
  status) for t in "${targets[@]}"; do f="$RUN_DIR/$t.pid"; if [[ -f "$f" ]] && kill -0 "$(cat "$f")" 2>/dev/null; then echo "$t running ($(cat "$f"))"; else echo "$t stopped"; fi; done ;;
  logs)   tail -n "${LINES_N:-20}" "$RUN_DIR/${targets[0]}.log" ;;
esac
