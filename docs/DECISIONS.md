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

## D-013 Invitations always email our own link (2026-09-28)
The plan sends new users through Supabase Auth invites and existing users a plain email. One path is
simpler: every invitation is a plain SMTP email with `/invite/<token>`; a recipient without an account
creates one from that page (email prefilled) and then accepts. SMTP is Mailpit locally
(`smtp_port = 54325` enabled in `config.toml`) and SES in hosted environments (`SMTP_*` settings).

## D-014 Own email type instead of EmailStr (2026-09-28)
`email-validator` rejects reserved TLDs such as `.local`, which the seeded demo accounts and tests use.
`app.domain.common.EmailAddress` lowercases and checks the shape only.

## D-015 pid-file dev server controller (2026-09-28)
`scripts/devctl.sh start|stop|status` runs api, worker, and web in the background with pid files. Used
by automation and by Playwright's webServer hook via `scripts/e2e-api.sh`; `make dev` remains the
foreground runner for people.

## D-016 Generated client treats defaulted fields as optional (2026-09-28)
`openapi-typescript` runs with `--default-non-nullable=false` so request bodies may omit fields that
have server-side defaults (for example workspace settings), matching the Pydantic schemas.

## D-017 Select policies do not filter deleted_at (2026-09-29)
Postgres checks the SELECT policy against the new row of an UPDATE, so a policy with `deleted_at is null`
rejects every soft delete. The predicate moved out of the policies; repositories and the read-model views
filter `deleted_at is null` on every read. Tenancy and visibility rules are unchanged.

## D-018 Application roles carry the extensions schema on their search_path (2026-09-29)
Supabase sets `search_path` on the `postgres` role only. `gravv_api` and `gravv_worker` get
`public, extensions` in migration 0009 so citext, pg_trgm operators, and `similarity()` resolve for
SQL run under `set local role authenticated`.

## D-020 Structured outputs through messages.parse (2026-09-29)
The plan forces structure with a single tool call. The current Anthropic API recommends `output_format` /
`messages.parse()`, and forced `tool_choice` is rejected on the newest model tier, so the provider uses
`parse()` with the Pydantic schema and retries once with the validation error appended. Default model is
`claude-opus-5` (override with `LLM_MODEL`). Server-side refusal fallbacks are not enabled; a refusal fails
the job with a clear capture error instead.

## D-021 The fake LLM is rule-based, with fixture overrides (2026-09-29)
A hash-selected fixture would return unrelated facts for arbitrary local input. `app/ai/fake.py` extracts
contacts, facts, tasks, people, and dates from the rendered prompt deterministically, so `make dev` without an
API key still produces sensible proposals and the e2e scenario is stable. Exact fixtures under
`tests/fixtures/ai/<prompt>/<hash>.json` override the rules when present.

## D-022 The worker role is also a member of authenticated (2026-09-29)
Extraction reads contacts under the practitioner's identity (RLS on), so `gravv_worker` needs
`set local role authenticated`. Migration 0009 grants both `service_role` and `authenticated` to it.

## D-023 Capture provenance is stored beside the proposal (2026-09-29)
`captures.proposal` holds `{extraction, provenance}`; provenance carries model, prompt version, inputs hash,
provider, and any auto-applied fact ids. The API returns the two as separate fields.
