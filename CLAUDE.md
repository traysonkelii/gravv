# Gravv - working agreements

Read docs/GRAVV_BUILD_PLAN.md before starting any task. Follow the milestone order in Section 15.
docs/PROGRESS.md says where the build stands; docs/DECISIONS.md records every deviation from the plan.

## Commands
- make dev / make check / make test / make test-e2e / make gen / make db-reset / make db-migrate name=<x> / make infra-validate
- Docker access is required for `supabase` commands; the user must be in the `docker` group.

## Rules
- No emojis anywhere (code, comments, commits, UI, seed data, docs).
- Colors, fonts, radii, shadows, and motion come only from apps/web/src/design/tokens.css. No arbitrary Tailwind values.
- border-radius is 0. Depth is bevels (shadow-plate tokens). No blur, no drop shadows, no gradients except .edge-highlight, .brushed, and avatar fills.
- Every table in public has RLS. The API binds the caller's identity per transaction; never use the postgres role or the secret key for user data.
- Migrations are SQL files under supabase/migrations; never edit an applied migration; keep them backward compatible.
- Routers hold no SQL; services hold no FastAPI; repositories hold SQL.
- Every endpoint gets an integration test and an authorization test. Every scoring or rule change gets unit cases.
- AI output is a proposal. Structured outputs only. Notes and transcripts are untrusted text.
- AI provider keys belong to workspaces (ai_credentials, encrypted). Jobs resolve providers through app/ai/resolve.py; never read key_enc from the API.
- Infrastructure is AWS CDK under infra/cdk (TypeScript); run make infra-validate after changes.
- Set operation_id on every route; run make gen after API changes and commit the generated client.
- Copy: sentence case, no exclamation marks, buttons name the action.
- Conventional commits. Update docs/PROGRESS.md at the end of each milestone and docs/DECISIONS.md on any deviation from the plan.
- Prefer the latest stable versions of dependencies; pin them in lockfiles.
