# Decisions and deviations from the build plan

ADR-style log. Newest at the bottom. Each entry: context, decision, consequence.

## D-001 Migration file names use timestamps (2026-09-28)
The plan shows `0001_...` names in Section 5 and timestamps in 5.8. The CLI sorts by the numeric prefix,
so files are `20260928000001_extensions_and_types.sql` through `...09_roles.sql`; the intent (one
migration per logical change, in order) is unchanged.

## D-002 Immutable wrapper for the contacts search vector (2026-09-28)
`array_to_string` is STABLE, and generated columns require IMMUTABLE expressions. `text_array_join()`
(migration 0001) wraps it.

## D-003 Trigger functions are security definer (2026-09-28)
`on_interaction_written`, `on_fact_written`, and `on_contact_created` update `contacts` and
`contact_profiles`. A member writing a note on a teammate's contact has no update right on that
contact row, so the triggers run as the owner. Without this the interaction insert fails under RLS.

## D-004 Role helpers live in the functions migration (2026-09-28)
`role_rank` and `is_member` are created in 0005 (not 0008) because `enqueue_job` depends on them.
Application roles are created idempotently in 0009 since roles survive `supabase db reset`.

## D-005 Column privilege on integrations.credentials_enc (2026-09-28)
A column-level REVOKE is ignored while a table-level SELECT grant exists. Migration 0008 revokes
table SELECT on `integrations` from `authenticated` and grants every column except `credentials_enc`.
Application code must never `select *` on `integrations`; the ORM model does not map the column.

## D-006 Security definer entry points instead of worker-role reads in the API (2026-09-28)
Invitation peek/accept, organization creation, job status, and audit writes go through
`security definer` functions granted to `authenticated` (and `anon` for peek). The API therefore
never uses the worker role or the secret key; public routes bind `set local role anon`.

## D-007 Seed runs after auth users exist (2026-09-28)
`seed.sql` references users by email, and users must be created through the auth admin API. The CLI's
automatic seeding is disabled in `config.toml` (`[db.seed] enabled = false`); `make db-reset` runs
`scripts/seed_users.py`, which creates the users and then executes `seed.sql`.

## D-008 Tests commit data instead of rolling back a wrapping transaction (2026-09-28)
Job handlers run on a separate worker connection and must see committed rows, so per-test rollback is
not viable. Integration tests create throwaway users (`test-*@test.gravv.local`) and the session
teardown deletes their workspaces and auth users.

## D-009 `make dev` uses a bash runner, not process-compose (2026-09-28)
`scripts/dev.sh` starts api, worker, and web with job control. One fewer tool to install.

## D-010 TypeScript pinned to 5.x (2026-09-28)
TypeScript 7 (the Go compiler) was the latest release when the web app was scaffolded; typescript-eslint
does not support it yet and it removed `baseUrl`. Revisit when typescript-eslint publishes support.

## D-011 Readiness check (2026-09-28)
`/readyz` verifies the database is reachable and that `public.is_member()` exists (migrations applied).
Comparing against the migration list would require shipping the migrations in the API image.

## D-012 HTTP clients for OpenAI-compatible providers (2026-09-28)
The OpenAI-compatible LLM and Whisper transcription providers use `httpx` directly instead of the
`openai` SDK. Both are a single POST each.
