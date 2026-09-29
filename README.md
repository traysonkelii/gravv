# Gravv

A relationship operating system for practitioners who need to track months or years of relationship
development. Monorepo: FastAPI + worker (`apps/api`), React PWA (`apps/web`), Supabase schema
(`supabase/`), Terraform (`infra/`).

The full specification is `docs/GRAVV_BUILD_PLAN.md`. Status per milestone is in `docs/PROGRESS.md`.

## Local development

Prerequisites: Docker (your user in the `docker` group), Supabase CLI, Python 3.12 + `uv`, Node 22 +
`pnpm` (via `corepack enable pnpm`), `make`.

```
make setup   # once: installs deps, starts Supabase, writes .env, resets and seeds the database
make dev     # api on :8000, worker, web on :5173
make check   # lint + tests + schema drift check (the milestone gate)
```

Sign in at http://127.0.0.1:5173 with `sarah@demo.gravv.local` / `demo-password-1`.
Magic links and invitations land in the local inbox at http://127.0.0.1:54324.

Without an Anthropic key the app runs with `LLM_PROVIDER=fake` and deterministic AI output.

## Deployment

`infra/terraform` holds staging and prod (App Runner, S3 + CloudFront, SSM, GitHub OIDC, alarms). `make infra-validate`
checks the configuration offline; `docs/RUNBOOK.md` walks through the first deployment and day-two operations.
GitHub Actions deploy staging on every merge to `main` and production on `v*` tags.
