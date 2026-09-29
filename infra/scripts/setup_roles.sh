#!/usr/bin/env bash
# Sets login + password on the application roles for one environment.
# Usage: infra/scripts/setup_roles.sh local            (uses the local Supabase container)
#        DB_URL=postgres://... infra/scripts/setup_roles.sh staging   (passwords from GRAVV_API_PASSWORD / GRAVV_WORKER_PASSWORD)
set -euo pipefail
env_name="${1:-local}"
if [[ "$env_name" == "local" ]]; then
  api_pw="${GRAVV_API_PASSWORD:-gravv_api_local}"
  worker_pw="${GRAVV_WORKER_PASSWORD:-gravv_worker_local}"
  sql="alter role gravv_api with password '$api_pw'; alter role gravv_worker with password '$worker_pw';"
  docker exec supabase_db_gravv psql -U postgres -d postgres -v ON_ERROR_STOP=1 -q -c "$sql"
else
  : "${DB_URL:?DB_URL is required for non-local environments}"
  : "${GRAVV_API_PASSWORD:?}" "${GRAVV_WORKER_PASSWORD:?}"
  psql "$DB_URL" -v ON_ERROR_STOP=1 -q \
    -c "alter role gravv_api with password '$GRAVV_API_PASSWORD';" \
    -c "alter role gravv_worker with password '$GRAVV_WORKER_PASSWORD';"
fi
echo "roles configured for $env_name"
