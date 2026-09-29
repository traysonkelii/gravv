#!/usr/bin/env bash
# Fails when any given text file contains emoji code points.
set -uo pipefail
status=0
for f in "$@"; do
  [[ -f "$f" ]] || continue
  case "$f" in *.png|*.jpg|*.jpeg|*.webp|*.ico|*.woff|*.woff2|*.lock|pnpm-lock.yaml) continue;; esac
  if grep -qP '[\x{1F300}-\x{1FAFF}\x{2600}-\x{27BF}\x{1F000}-\x{1F2FF}\x{FE0F}]' "$f" 2>/dev/null; then
    echo "emoji found in $f"; status=1
  fi
done
exit $status
