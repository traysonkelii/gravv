#!/usr/bin/env bash
# Writes .env from .env.example and the running local Supabase stack. Existing .env is left alone.
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ -f .env ]]; then echo ".env exists, leaving it alone"; exit 0; fi
eval "$(supabase status -o env 2>/dev/null | grep -E '^(PUBLISHABLE_KEY|SECRET_KEY|JWT_SECRET)=')"
enc_key="$(head -c 32 /dev/urandom | base64)"
sed -e "s|^SUPABASE_PUBLISHABLE_KEY=.*|SUPABASE_PUBLISHABLE_KEY=${PUBLISHABLE_KEY}|" \
    -e "s|^SUPABASE_SECRET_KEY=.*|SUPABASE_SECRET_KEY=${SECRET_KEY}|" \
    -e "s|^SUPABASE_JWT_SECRET=.*|SUPABASE_JWT_SECRET=${JWT_SECRET}|" \
    -e "s|^APP_ENCRYPTION_KEY=.*|APP_ENCRYPTION_KEY=${enc_key}|" \
    -e "s|^VITE_SUPABASE_PUBLISHABLE_KEY=.*|VITE_SUPABASE_PUBLISHABLE_KEY=${PUBLISHABLE_KEY}|" \
    .env.example > .env
echo "wrote .env"
