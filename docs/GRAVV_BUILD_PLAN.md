# Gravv (6 Degrees) - Full-Stack Build Plan

Working title: **Gravv** (the mockups) / **6 Degrees (6°)** (the concept document).
Repository name: `gravv`.

This document is the single source of truth for building Gravv: a Relationship Operating System for practitioners (sales, program management, diplomacy, consulting, lobbying) who need to track the months or years of relationship development that CRMs ignore. It is written to be handed to a Claude Code instance and executed milestone by milestone.

---

## 0. How to use this document (read first)

1. Save this file as `docs/GRAVV_BUILD_PLAN.md` in the repository; `CLAUDE.md` (Appendix C) points to it. Work through the milestones in Section 15 in order. Do not start a later milestone until the acceptance criteria of the current one pass locally.
2. Every milestone ends with `make check` (lint, type-check, unit and integration tests) passing and a commit.
3. When this plan and reality conflict (a library API changed, a Supabase CLI flag was renamed), prefer the current upstream documentation, keep the intent of the plan, and record the deviation in `docs/DECISIONS.md`.
4. Pin dependency versions to the latest stable release at the time of implementation. Do not downgrade to match a version mentioned anywhere in this document; this plan is intentionally version-agnostic.
5. Non-negotiables:
   - No emojis anywhere: UI copy, code, comments, commit messages, seed data, docs.
   - No infrastructure beyond what Section 13 lists. If a feature seems to need Redis, Kafka, or a queue service, use the Postgres-backed job table (Section 7.6) instead.
   - Row Level Security (RLS) is enabled on every table in `public`. The API runs queries under the caller's identity (Section 6.4). There is no code path that reads tenant data without RLS except the worker's explicitly scoped jobs.
   - All AI output is a proposal until a human confirms it, with the exceptions listed in Section 11.5.
   - The design system in Section 10 is mandatory. Do not introduce colors, radii, fonts, or shadows that are not tokens.
   - Everything must run and be tested locally with `make dev` and `make check` before any cloud resource exists.

---

## 1. Product summary

### 1.1 What Gravv does

Gravv captures the three things a practitioner needs at the point of contact:

| Element | Meaning | Where it lives |
| --- | --- | --- |
| The essence of the contact | Personality profile: likes, dislikes, communication style, personal stories, ambitions, corporate context | `contact_facts` + AI-synthesized `contact_profiles` |
| The history of the relationship | Scrollable timeline of notes, meetings, calls, emails, key moments; due-outs and gaps | `interactions`, `tasks`, `relationship_scores` |
| The context of the discussion | News and signals about the person, their company, and their market | `context_items` (Phase 3) + `insights` |

Practitioners enter information fast (typed or spoken). The system parses it with an LLM, extracts facts, action items, and sentiment, and keeps a relationship health score ("Gravity") current. Managers get an enterprise view of who and what performs.

### 1.2 Reference scenario (from the concept document)

Sarah, a new Account Executive, inherits the Space Force account. She asks Gravv for the status of every relationship in play, gets a briefing (pitfalls, due-outs, upcoming meetings, notable moments), pulls the Colonel's profile (Diet Coke, North Carolina BBQ), and after the meeting taps to talk: "Update the meeting note, add that he is a competitive pinball fanatic, remind me to contact the program officers he mentioned, and remind me to book the next meeting at a pinball bar." Gravv creates the interaction, the facts, and the tasks, and syncs the note to her CRM.

Every feature in this plan traces back to this scenario or to the five mockups.

### 1.3 Mockup inventory and what each becomes

| Mockup file | Becomes | Milestone |
| --- | --- | --- |
| `six-degrees-mobile.html` | App shell (mobile-first), Home dashboard, Contacts list, Contact detail (Overview / History / Notes), voice capture | M2, M3 |
| `analytics-dashboard.html` | Analytics page (metrics row, distribution and frequency charts, top relationships table, insight cards) plus Team tab for managers | M4, M6 |
| `network-visualization.html` | Network page (force-directed canvas, filters, node info panel, path finder) | M5 |
| `gravv-onboarding.html` | Onboarding wizard (profile, interests, goals, integrations, done) | M1 |
| `six-degrees-homepage.html` | Public landing page at `/` (low priority, static) | M7 |

Things in the mockups that are explicitly out of scope for v1: 3D network view, live CRM/email/LinkedIn sync (stubbed as "available soon" in onboarding), marketing stats on the landing page (replace with product truth), and every emoji.

### 1.4 Vocabulary (brand metaphor vs. plain language)

The brand uses a gravity metaphor. Use it in exactly two places and use plain language everywhere else, so new users can navigate without learning a lexicon.

| Concept | UI term | Internal name |
| --- | --- | --- |
| Relationship health score 0-100 | Gravity | `gravity_score` |
| Expected contact cadence | Orbit (e.g. "30-day orbit") | `cadence_days` |
| Count of active contacts | Contacts (mockup: "Network Mass") | `contact_count` |
| Mean Gravity | Average gravity (mockup: "Gravity Pull") | `avg_gravity` |
| Tasks and cadences due | Due this week (mockup: "Orbits Due") | `due_count` |
| Sum of open opportunity value | Pipeline (mockup: "Gravity Well") | `pipeline_value` |
| Score bands | Strong (70+), Steady (40-69), Weak (<40), Drifting (past 2x cadence) | `band` |
| Profile facts a practitioner should remember | Notes to remember (mockup: "Attraction Points") | `contact_facts` |
| Communication style | Style (mockup: "Orbital Pattern") | `communication_style` |

If the product owner prefers the full metaphor, the labels are a single i18n file (`apps/web/src/lib/copy.ts`); change them there only.

---

## 2. Architecture overview

### 2.1 Diagram

```
                        +----------------------------------+
                        |  Browser / Mobile PWA            |
                        |  React + TypeScript + Vite       |
                        |  supabase-js (auth only)         |
                        +-----------+----------+-----------+
                                    |          |
              Supabase Auth (JWT)   |          |  HTTPS, Bearer JWT
                                    |          v
+---------------------+   +---------+-----------------------------+
| Supabase (hosted or |   |  FastAPI  (apps/api)                  |
| local via CLI)      |<--+  - verifies JWT (JWKS / HS256)       |
|  - Postgres + RLS   |   |  - runs SQL as `authenticated` with  |
|  - Auth             |   |    request.jwt.claims set (RLS on)   |
|  - Storage (audio,  |   |  - business logic, scoring, AI       |
|    exports, avatars)|   |  - enqueues jobs into `jobs` table   |
|  - Realtime (later) |   +---------+-----------------------------+
+----------+----------+             |
           ^                        v
           |              +---------+-----------------------------+
           +--------------+  Worker (apps/api, `python -m app.worker`)
                          |  - polls `jobs` (FOR UPDATE SKIP LOCKED)
                          |  - transcription, LLM extraction,      |
                          |    profile synthesis, scoring,         |
                          |    insights, exports, integration sync |
                          +---------+-----------------------------+
                                    |
                                    v
                          External: Anthropic API (LLM), transcription
                          provider (OpenAI Whisper API / Deepgram),
                          later: Gmail/Outlook/Calendar/CRM APIs
```

One codebase for API and worker. One database. One managed auth. No queues, caches, or brokers.

### 2.2 Stack decisions and rationale

| Layer | Choice | Why | Rejected alternatives |
| --- | --- | --- | --- |
| Database | Postgres via Supabase (pgvector, pg_trgm, citext, pg_cron optional) | RLS-native multi-tenancy, managed backups, runs identically locally through the Supabase CLI | Bare RDS (more ops), DynamoDB (poor fit for relational graph data) |
| Auth | Supabase Auth: email+password, magic link, Google and Microsoft OAuth, TOTP MFA | Zero auth code to own; JWTs verifiable in FastAPI; OAuth providers double as future integration identities | Auth0/Clerk (another vendor), self-rolled auth (risk) |
| Backend | FastAPI, Python 3.12+, Pydantic v2, SQLAlchemy 2.0 async + asyncpg | One language for API, worker, and AI code; typed request/response; OpenAPI drives the frontend client | Node/Nest (splits AI tooling), Django (heavier) |
| Migrations | Plain SQL managed by Supabase CLI (`supabase/migrations`) | RLS policies, triggers, and `auth.users` hooks are SQL; the CLI applies them locally, in CI, and to hosted projects | Alembic autogenerate (fights with RLS and Supabase-owned schemas) |
| Background work | Postgres job table + worker process | Durable, transactional with app data, zero extra infrastructure, scales by adding workers | Celery+Redis, SQS (add later if needed, Section 14) |
| AI | Anthropic Claude via the `anthropic` SDK behind a provider interface; structured outputs with Pydantic schemas | Strong extraction and summarization; provider interface keeps OpenAI-compatible and a `FakeLLM` for tests | Direct SDK calls scattered through code |
| Transcription | Provider interface: OpenAI Whisper API or Deepgram in prod; `faster-whisper` or fake locally | Practitioner tap-to-talk is the core capture path | Browser speech-to-text only (unreliable, no audio record) |
| Frontend | React + TypeScript + Vite, React Router, TanStack Query, Zustand (small UI state), react-hook-form + zod, Tailwind v4 with CSS-first tokens, Lucide icons, Recharts, d3-force (canvas), vite-plugin-pwa | Mobile-first PWA installable on phones today; native wrapper (Capacitor) later without a rewrite | Next.js (SSR unneeded, complicates static hosting), React Native now (doubles UI work) |
| API client | Generated from FastAPI OpenAPI via `openapi-typescript` + `openapi-fetch` | Types never drift from the backend | Hand-written fetchers |
| Hosting | Supabase hosted (same AWS region), AWS App Runner for API and worker, S3 + CloudFront for the SPA, Terraform | Lowest-overhead AWS path with a clean upgrade to ECS Fargate/VPC | Kubernetes, Amplify, Vercel (not AWS) |
| CI/CD | GitHub Actions with OIDC to AWS | No long-lived cloud keys | Jenkins |
| Observability | structlog JSON logs to CloudWatch, request IDs, Sentry (optional), health endpoints | Enough for early stage; OpenTelemetry hook later | Datadog (cost) |

### 2.3 Data ownership model (from the concept document)

- Every user gets a **personal workspace** at sign-up. Personal data is theirs and is never visible to anyone else.
- Users can belong to one or more **organization workspaces** with a role. Data created inside an organization workspace belongs to the organization.
- A user can **share** a personal contact into an organization (creates an organization-owned copy linked by `origin_contact_id`), and can **copy** any contact they authored in an organization back to their personal workspace at any time. Both parties retain what they need.
- On departure, the membership becomes `departed` with a `grace_until` date; the user loses access to the organization workspace immediately, keeps their personal workspace, and the organization keeps everything created inside it. Billing during the grace period is out of scope for v1 but the field exists.

---

## 3. Repository layout (monorepo)

```
gravv/
  README.md
  CLAUDE.md                      # conventions for Claude Code (Appendix C)
  Makefile                       # dev, check, test, seed, gen, deploy targets
  .env.example
  .github/workflows/
    ci.yml                       # lint, type-check, tests, build
    deploy-staging.yml
    deploy-prod.yml
  docs/
    DECISIONS.md                 # ADR-style log of deviations and choices
    PROGRESS.md                  # milestone status, updated per milestone
    design/                      # exported design references (no binaries > 1MB)
  supabase/
    config.toml                  # Supabase CLI config (local ports, auth settings)
    migrations/                  # timestamped SQL migrations (Section 5)
    seed.sql                     # demo data for local dev and e2e (Section 4.5)
    functions/                   # (empty in v1; edge functions not used)
  apps/
    api/                         # FastAPI service + worker (one package)
      pyproject.toml             # managed with uv
      app/
        main.py                  # FastAPI app factory, routers, middleware
        config.py                # pydantic-settings
        db/
          session.py             # engine, session factory, RLS-bound session
          models/                # SQLAlchemy models mirroring migrations
          repositories/          # query functions per aggregate
        auth/
          jwt.py                 # JWKS/HS256 verification
          deps.py                # get_current_user, require_role
        domain/
          contacts/  companies/  interactions/  facts/  tasks/
          opportunities/  insights/  analytics/  network/
          workspaces/  capture/  integrations/  exports/
            router.py schemas.py service.py
        ai/
          llm.py                 # provider interface + Anthropic, OpenAI-compatible, Fake
          transcription.py       # provider interface + OpenAI, Deepgram, Fake
          prompts/               # versioned prompt templates
          extraction.py profile.py briefing.py narration.py
        scoring/
          gravity.py             # deterministic score engine
          rules.py               # insight detection rules
        jobs/
          queue.py               # enqueue, claim, complete, fail
          handlers/              # one module per job kind
          scheduler.py           # recurring job enqueueing
        worker.py                # entrypoint: python -m app.worker
        storage.py               # Supabase Storage signed URLs
        observability.py         # logging, request id, metrics
        errors.py                # Problem Details responses
      scripts/
        export_openapi.py        # dumps openapi.json for client generation
        seed_users.py            # creates seed users through the Supabase admin API
      tests/
        conftest.py              # local Supabase DB, RLS fixtures, fake AI
        unit/ integration/ rls/ ai/
      Dockerfile
    web/                         # React SPA (PWA)
      package.json               # managed with pnpm
      index.html
      vite.config.ts
      src/
        main.tsx app.tsx routes.tsx
        lib/
          api/                   # generated client + typed wrappers
          supabase.ts auth.tsx copy.ts format.ts
        design/
          tokens.css             # Section 10 tokens (single source)
          fonts.css
        components/ui/           # primitives (Button, Field, Table, ...)
        components/shell/        # AppShell, BottomNav, SideRail, TopBar
        features/
          auth/ onboarding/ home/ contacts/ capture/ insights/
          network/ analytics/ tasks/ opportunities/ settings/ landing/
        hooks/ utils/
      tests/                     # vitest + testing-library
      e2e/                       # playwright
      Dockerfile                 # nginx static (used for local docker parity only)
  infra/
    terraform/
      modules/ (apprunner, ecr, static-site, secrets, github-oidc, alarms)
      envs/staging/ envs/prod/
    scripts/                     # one-off ops scripts (role passwords, bucket setup)
  docker-compose.yml             # api + worker + web containers (Supabase runs via CLI)
```

Tooling: `uv` for Python, `pnpm` for Node, `ruff` + `mypy --strict` for Python, `eslint` + `tsc --noEmit` + `prettier` for TypeScript, `pre-commit` hooks for both.

---
## 4. Local development

### 4.1 Prerequisites

- Docker Desktop (or compatible) running.
- Supabase CLI (`brew install supabase/tap/supabase` or `npm i -g supabase`).
- Python 3.12+ and `uv`.
- Node 22+ and `pnpm`.
- `make`.
- Optional: an Anthropic API key. Without it, set `LLM_PROVIDER=fake` and the whole app still runs with deterministic fake AI output.

### 4.2 Ports (Supabase CLI defaults; keep them)

| Service | URL |
| --- | --- |
| Supabase API gateway (Auth, PostgREST, Storage) | http://127.0.0.1:54321 |
| Postgres | postgresql://postgres:postgres@127.0.0.1:54322/postgres |
| Supabase Studio | http://127.0.0.1:54323 |
| Email testing inbox (Mailpit/Inbucket) for magic links and invites | http://127.0.0.1:54324 |
| FastAPI | http://127.0.0.1:8000 (docs at /docs) |
| Worker | no port; logs to stdout |
| Web (Vite) | http://127.0.0.1:5173 |

### 4.3 Make targets

```make
setup:      ## one-time: uv sync, pnpm install, pre-commit install, supabase start, db reset, roles, seed
dev:        ## supabase start (if needed) + api (uvicorn --reload) + worker + web, via process-compose or foreman-style runner
db-reset:   ## supabase db reset (drops, re-applies all migrations, runs seed.sql) then scripts/db/setup_roles.sh
db-migrate: ## supabase migration new <name>   (usage: make db-migrate name=add_tasks)
db-diff:    ## supabase db diff  (must be empty in CI; detects hand edits made in Studio)
gen:        ## export OpenAPI from FastAPI and regenerate apps/web/src/lib/api/schema.d.ts
seed:       ## psql -f supabase/seed.sql
test:       ## pytest (api) + vitest (web)
test-e2e:   ## playwright against the local stack
lint:       ## ruff check, ruff format --check, mypy, eslint, prettier --check, tsc --noEmit
check:      ## lint + test + db-diff (the gate for every milestone)
build:      ## docker build api; pnpm build web
```

Run `make setup` once, then `make dev`. `make dev` must be a single command that leaves a developer with a working login at http://127.0.0.1:5173 using the seeded user `sarah@demo.gravv.local` / `demo-password-1` (seed users are created through the Supabase admin API in `scripts/seed_users.py`, never by inserting into `auth.users` directly).

### 4.4 Environment variables

Copy `.env.example` to `.env` at the repo root; both apps read it in local mode.

```dotenv
# shared
APP_ENV=local                      # local | test | staging | production

# api + worker
DATABASE_URL=postgresql+asyncpg://gravv_api:gravv_api_local@127.0.0.1:54322/postgres
DATABASE_URL_WORKER=postgresql+asyncpg://gravv_worker:gravv_worker_local@127.0.0.1:54322/postgres
SUPABASE_URL=http://127.0.0.1:54321
SUPABASE_PUBLISHABLE_KEY=          # from `supabase status` (legacy name: anon key)
SUPABASE_SECRET_KEY=               # from `supabase status` (legacy name: service_role key); server only
SUPABASE_JWT_SECRET=               # from `supabase status`; used only when tokens are HS256
CORS_ORIGINS=http://127.0.0.1:5173,http://localhost:5173
APP_ENCRYPTION_KEY=                # 32 random bytes, base64; encrypts integration credentials
LLM_PROVIDER=fake                  # anthropic | openai | fake
LLM_MODEL=                         # provider model id; leave empty for provider default
ANTHROPIC_API_KEY=
OPENAI_API_KEY=
TRANSCRIPTION_PROVIDER=fake        # openai | deepgram | fake
DEEPGRAM_API_KEY=
STORAGE_BUCKET_VOICE=voice-notes
STORAGE_BUCKET_EXPORTS=exports
STORAGE_BUCKET_AVATARS=avatars
WORKER_CONCURRENCY=4
WORKER_POLL_INTERVAL_SECONDS=2
RATE_LIMIT_PER_MINUTE=120
LOG_LEVEL=INFO
SENTRY_DSN=

# web (Vite exposes only VITE_* to the browser)
VITE_SUPABASE_URL=http://127.0.0.1:54321
VITE_SUPABASE_PUBLISHABLE_KEY=
VITE_API_URL=http://127.0.0.1:8000
```

Never put `SUPABASE_SECRET_KEY`, `APP_ENCRYPTION_KEY`, or provider API keys in the web app.

### 4.5 Seed data

`supabase/seed.sql` plus `scripts/seed_users.py` create:

- Users: Sarah Chen (Account Executive, owner of org "Meridian Components"), Dan Okafor (manager), Priya Nair (member). Each also has a personal workspace with two private contacts.
- Companies: Space Force (government), U.S. Army (government), Boeing, Lockheed Martin, Northrop Grumman, NASA, TechCorp Solutions.
- Contacts (from the mockups): Col. Michael Johnson (Space Force, Program Director; facts: Diet Coke, North Carolina BBQ, competitive pinball; style: direct and formal), Emily Rodriguez (Boeing, Contract Manager), Sarah Martinez (Lockheed Martin, VP Sales; drifting), Lisa Wong (Northrop Grumman, VP Engineering), Dr. James Chen (NASA, Chief Scientist), Kevin Liu (TechCorp, CTO), Gen. Patricia Williams, Dr. Robert Stevens, Amanda Brooks, Thomas Miller.
- 60-90 days of interactions spread across contacts with varied kinds and sentiment so that scores, bands, distribution charts, and insight rules all produce visible output.
- Contact-to-contact relationships matching the mockup graph edges.
- Two open opportunities (Phase 2 Satellite Program $2.5M; Boeing subcontract $3.2M).
- Open tasks, some overdue.

Seed data contains no emojis and no placeholder lorem text; every note reads like a real practitioner wrote it.

---

## 5. Database design

Schema lives in `supabase/migrations/*.sql`. One migration per logical change, numbered by the CLI. Never edit a migration that has been applied to staging or prod; add a new one.

### 5.1 Conventions

- Primary keys: `uuid default gen_random_uuid()`.
- Timestamps: `timestamptz`, `created_at default now()`, `updated_at` maintained by trigger `set_updated_at()`.
- Soft delete where users expect undo: `deleted_at timestamptz` on `contacts`, `companies`, `interactions`, `opportunities`. All read queries filter `deleted_at is null`.
- Money: `bigint` cents + `currency char(3) default 'USD'`.
- Tenancy: every business table carries `workspace_id uuid not null references workspaces(id)`; RLS predicates use it.
- Text search: `search_vector tsvector` generated column on `contacts` and `interactions`; `pg_trgm` GIN index for fuzzy name search.
- Enums are Postgres enums (add values with `alter type ... add value`), listed in 5.2.
- Naming: snake_case, plural table names, `*_id` foreign keys, `idx_<table>_<cols>` indexes, `<table>_<action>` policy names.

### 5.2 Extensions and enums (`0001_extensions_and_types.sql`)

```sql
create extension if not exists pgcrypto with schema extensions;
create extension if not exists citext with schema extensions;
create extension if not exists pg_trgm with schema extensions;
create extension if not exists vector with schema extensions;

create type workspace_kind      as enum ('personal', 'organization');
create type workspace_role      as enum ('viewer', 'member', 'manager', 'admin', 'owner');
create type membership_status   as enum ('invited', 'active', 'departed');
create type company_type        as enum ('client', 'partner', 'vendor', 'government', 'prospect', 'other');
create type relationship_type   as enum ('client', 'partner', 'vendor', 'colleague', 'government', 'other');
create type contact_visibility  as enum ('private', 'team');
create type contact_status      as enum ('active', 'follow_up', 'needs_attention', 'drifting', 'archived');
create type fact_category       as enum ('preference', 'dislike', 'interest', 'personal', 'professional', 'communication_style', 'ambition', 'family', 'risk', 'other');
create type fact_source         as enum ('manual', 'note', 'voice', 'email', 'calendar', 'crm', 'ai');
create type interaction_kind    as enum ('note', 'meeting', 'call', 'email', 'message', 'event', 'introduction', 'gift', 'other');
create type interaction_direction as enum ('inbound', 'outbound', 'mutual');
create type interaction_source  as enum ('manual', 'voice', 'gmail', 'outlook', 'google_calendar', 'ms_calendar', 'crm', 'import');
create type ai_status           as enum ('none', 'pending', 'processed', 'failed', 'skipped');
create type task_status         as enum ('open', 'done', 'snoozed', 'cancelled');
create type task_source         as enum ('manual', 'ai', 'voice', 'cadence');
create type opportunity_status  as enum ('open', 'won', 'lost', 'on_hold');
create type opportunity_role    as enum ('decision_maker', 'influencer', 'champion', 'blocker', 'user', 'other');
create type edge_kind           as enum ('knows', 'reports_to', 'works_with', 'introduced_by', 'former_colleague', 'other');
create type insight_kind        as enum ('follow_up', 'at_risk', 'opportunity_signal', 'introduction_path', 'trend', 'briefing', 'common_ground');
create type insight_status      as enum ('new', 'seen', 'acted', 'dismissed', 'expired');
create type insight_severity    as enum ('info', 'notice', 'warning');
create type capture_status      as enum ('uploaded', 'transcribing', 'transcribed', 'extracting', 'proposed', 'confirmed', 'discarded', 'failed');
create type job_status          as enum ('queued', 'running', 'succeeded', 'failed', 'dead');
create type integration_provider as enum ('gmail', 'outlook', 'google_calendar', 'ms_calendar', 'salesforce', 'hubspot', 'slack', 'linkedin');
create type integration_status  as enum ('connected', 'needs_reauth', 'disabled', 'error');
create type sentiment_label     as enum ('positive', 'neutral', 'negative', 'mixed');
```

### 5.3 Identity and tenancy tables (`0002_identity.sql`)

```sql
create table profiles (
  id                       uuid primary key references auth.users(id) on delete cascade,
  email                    citext not null unique,
  full_name                text not null default '',
  role_title               text,
  timezone                 text not null default 'UTC',
  avatar_path              text,
  goals                    jsonb not null default '{}'::jsonb,   -- {"close_deals":true,"expand_network":false,"strengthen":true,"track_roi":false,"free_text":"..."}
  onboarding_step          smallint not null default 0,          -- 0..5, 5 = complete
  onboarding_completed_at  timestamptz,
  default_workspace_id     uuid,                                 -- fk added after workspaces exists
  deleted_at               timestamptz,                          -- tombstone after account deletion (Section 6.6)
  created_at               timestamptz not null default now(),
  updated_at               timestamptz not null default now()
);

create table user_interests (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null references profiles(id) on delete cascade,
  kind        text not null check (kind in ('professional', 'personal')),
  value       citext not null,
  created_at  timestamptz not null default now(),
  unique (user_id, kind, value)
);

create table workspaces (
  id             uuid primary key default gen_random_uuid(),
  kind           workspace_kind not null,
  name           text not null,
  slug           citext unique,                        -- null for personal workspaces
  owner_user_id  uuid not null references profiles(id),
  settings       jsonb not null default '{}'::jsonb,   -- {"default_contact_visibility":"team","default_cadence_days":30,"auto_apply_low_risk_facts":false}
  plan           text not null default 'free',
  created_at     timestamptz not null default now(),
  updated_at     timestamptz not null default now()
);
alter table profiles add constraint profiles_default_workspace_fk
  foreign key (default_workspace_id) references workspaces(id) on delete set null;

create table memberships (
  id            uuid primary key default gen_random_uuid(),
  workspace_id  uuid not null references workspaces(id) on delete cascade,
  user_id       uuid not null references profiles(id) on delete cascade,
  role          workspace_role not null default 'member',
  status        membership_status not null default 'active',
  joined_at     timestamptz not null default now(),
  departed_at   timestamptz,
  grace_until   timestamptz,
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now(),
  unique (workspace_id, user_id)
);
create index idx_memberships_user_active on memberships (user_id) where status = 'active';

create table invitations (
  id            uuid primary key default gen_random_uuid(),
  workspace_id  uuid not null references workspaces(id) on delete cascade,
  email         citext not null,
  role          workspace_role not null default 'member',
  token_hash    text not null unique,                 -- sha256 of the raw token sent by email
  invited_by    uuid not null references profiles(id),
  expires_at    timestamptz not null default now() + interval '7 days',
  accepted_at   timestamptz,
  created_at    timestamptz not null default now()
);
create index idx_invitations_workspace_email on invitations (workspace_id, email);
```

Trigger that provisions every new auth user (profile + personal workspace + owner membership):

```sql
create or replace function public.handle_new_user()
returns trigger language plpgsql security definer set search_path = public as $$
declare ws_id uuid;
begin
  insert into profiles (id, email, full_name)
  values (new.id, new.email, coalesce(new.raw_user_meta_data->>'full_name', ''));
  insert into workspaces (kind, name, owner_user_id)
  values ('personal', 'Personal', new.id) returning id into ws_id;
  insert into memberships (workspace_id, user_id, role, status)
  values (ws_id, new.id, 'owner', 'active');
  update profiles set default_workspace_id = ws_id where id = new.id;
  return new;
end $$;

create trigger on_auth_user_created
after insert on auth.users for each row execute function public.handle_new_user();
```

### 5.4 Relationship data tables (`0003_core.sql`)

```sql
create table companies (
  id            uuid primary key default gen_random_uuid(),
  workspace_id  uuid not null references workspaces(id) on delete cascade,
  name          text not null,
  domain        citext,
  industry      text,                                   -- free text; suggestions: aerospace, defense, tech, government, healthcare, finance
  type          company_type not null default 'other',
  notes         text,
  created_by    uuid not null references profiles(id),
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now(),
  deleted_at    timestamptz
);
create index idx_companies_workspace_name on companies (workspace_id, lower(name));

create table contacts (
  id                   uuid primary key default gen_random_uuid(),
  workspace_id         uuid not null references workspaces(id) on delete cascade,
  owner_user_id        uuid not null references profiles(id),
  company_id           uuid references companies(id) on delete set null,
  first_name           text not null default '',
  last_name            text not null default '',
  display_name         text generated always as (btrim(first_name || ' ' || last_name)) stored,
  honorific            text,                             -- Col., Dr., Gen.
  title                text,
  emails               citext[] not null default '{}',
  phones               text[] not null default '{}',
  location             text,
  relationship_type    relationship_type not null default 'other',
  visibility           contact_visibility not null default 'team',
  status               contact_status not null default 'active',
  tags                 text[] not null default '{}',
  cadence_days         smallint not null default 30 check (cadence_days between 1 and 365),
  gravity_score        smallint not null default 0 check (gravity_score between 0 and 100),
  gravity_updated_at   timestamptz,
  last_interaction_at  timestamptz,
  next_due_at          timestamptz,                      -- earliest of open task due or cadence due; maintained by scoring job
  origin_contact_id    uuid references contacts(id) on delete set null, -- set when copied/shared across workspaces
  source               text not null default 'manual',
  search_vector        tsvector generated always as (
                         to_tsvector('simple', coalesce(first_name,'') || ' ' || coalesce(last_name,'') || ' ' || coalesce(title,'') || ' ' || array_to_string(tags, ' '))
                       ) stored,
  created_at           timestamptz not null default now(),
  updated_at           timestamptz not null default now(),
  deleted_at           timestamptz
);
create index idx_contacts_workspace_status on contacts (workspace_id, status) where deleted_at is null;
create index idx_contacts_workspace_owner  on contacts (workspace_id, owner_user_id) where deleted_at is null;
create index idx_contacts_company          on contacts (company_id);
create index idx_contacts_search           on contacts using gin (search_vector);
create index idx_contacts_name_trgm        on contacts using gin (display_name gin_trgm_ops);
create index idx_contacts_next_due         on contacts (workspace_id, next_due_at) where deleted_at is null and status <> 'archived';

create table contact_facts (
  id             uuid primary key default gen_random_uuid(),
  workspace_id   uuid not null references workspaces(id) on delete cascade,
  contact_id     uuid not null references contacts(id) on delete cascade,
  category       fact_category not null,
  content        text not null check (length(content) between 1 and 500),
  confidence     real not null default 1.0 check (confidence between 0 and 1),
  source         fact_source not null default 'manual',
  source_interaction_id uuid,                            -- fk added after interactions
  is_active      boolean not null default true,
  superseded_by  uuid references contact_facts(id),
  created_by     uuid not null references profiles(id),
  created_at     timestamptz not null default now(),
  updated_at     timestamptz not null default now()
);
create index idx_contact_facts_contact_active on contact_facts (contact_id) where is_active;

create table contact_profiles (                            -- one AI-synthesized snapshot per contact
  contact_id           uuid primary key references contacts(id) on delete cascade,
  workspace_id         uuid not null references workspaces(id) on delete cascade,
  summary              text not null default '',
  communication_style  text,
  remember             text[] not null default '{}',       -- short bullets: "Diet Coke", "NC-style BBQ", "competitive pinball"
  risks                text[] not null default '{}',
  talking_points       text[] not null default '{}',
  model                text,
  prompt_version       text,
  generated_at         timestamptz,
  stale                boolean not null default true,      -- set true whenever facts/interactions change
  updated_at           timestamptz not null default now()
);

create table interactions (
  id               uuid primary key default gen_random_uuid(),
  workspace_id     uuid not null references workspaces(id) on delete cascade,
  contact_id       uuid references contacts(id) on delete cascade,   -- null allowed while a capture is unassigned
  user_id          uuid not null references profiles(id),
  kind             interaction_kind not null default 'note',
  direction        interaction_direction not null default 'mutual',
  occurred_at      timestamptz not null default now(),
  subject          text,
  body             text not null default '',
  summary          text,                                              -- AI one-liner
  sentiment        sentiment_label,
  sentiment_score  real check (sentiment_score between -1 and 1),
  source           interaction_source not null default 'manual',
  external_id      text,                                              -- gmail message id, calendar event id, crm activity id
  ai_status        ai_status not null default 'none',
  ai_extraction    jsonb,                                             -- last CaptureExtraction payload (Section 11.2)
  metadata         jsonb not null default '{}'::jsonb,
  search_vector    tsvector generated always as (to_tsvector('english', coalesce(subject,'') || ' ' || coalesce(body,''))) stored,
  embedding        extensions.vector(1536),                           -- nullable; filled by Phase 2 job
  created_at       timestamptz not null default now(),
  updated_at       timestamptz not null default now(),
  deleted_at       timestamptz,
  unique (workspace_id, source, external_id)
);
create index idx_interactions_contact_time on interactions (contact_id, occurred_at desc) where deleted_at is null;
create index idx_interactions_workspace_time on interactions (workspace_id, occurred_at desc) where deleted_at is null;
create index idx_interactions_search on interactions using gin (search_vector);
alter table contact_facts add constraint contact_facts_source_interaction_fk
  foreign key (source_interaction_id) references interactions(id) on delete set null;

create table captures (                                  -- a single tap-to-talk or quick-note session
  id             uuid primary key default gen_random_uuid(),
  workspace_id   uuid not null references workspaces(id) on delete cascade,
  user_id        uuid not null references profiles(id),
  contact_id     uuid references contacts(id) on delete set null,
  kind           text not null check (kind in ('voice', 'text')),
  storage_path   text,                                   -- voice: <workspace_id>/<user_id>/<capture_id>.webm
  duration_seconds real,
  transcript     text,
  raw_text       text,                                   -- text captures
  status         capture_status not null default 'uploaded',
  proposal       jsonb,                                  -- CaptureExtraction awaiting confirmation
  interaction_id uuid references interactions(id) on delete set null,
  error          text,
  idempotency_key text,
  created_at     timestamptz not null default now(),
  updated_at     timestamptz not null default now(),
  unique (user_id, idempotency_key)
);
create index idx_captures_user_status on captures (user_id, status, created_at desc);

create table tasks (
  id                    uuid primary key default gen_random_uuid(),
  workspace_id          uuid not null references workspaces(id) on delete cascade,
  assignee_user_id      uuid not null references profiles(id),
  contact_id            uuid references contacts(id) on delete cascade,
  title                 text not null check (length(title) between 1 and 200),
  description           text,
  due_at                timestamptz,
  status                task_status not null default 'open',
  priority              smallint not null default 2 check (priority between 1 and 3),  -- 1 high, 2 normal, 3 low
  source                task_source not null default 'manual',
  source_interaction_id uuid references interactions(id) on delete set null,
  completed_at          timestamptz,
  snoozed_until         timestamptz,
  created_by            uuid not null references profiles(id),
  created_at            timestamptz not null default now(),
  updated_at            timestamptz not null default now()
);
create index idx_tasks_assignee_open on tasks (assignee_user_id, due_at) where status = 'open';
create index idx_tasks_contact on tasks (contact_id);

create table opportunities (
  id               uuid primary key default gen_random_uuid(),
  workspace_id     uuid not null references workspaces(id) on delete cascade,
  company_id       uuid references companies(id) on delete set null,
  owner_user_id    uuid not null references profiles(id),
  name             text not null,
  value_cents      bigint not null default 0 check (value_cents >= 0),
  currency         char(3) not null default 'USD',
  stage            text not null default 'qualifying',   -- free text stages; workspace settings may define the list
  probability      smallint check (probability between 0 and 100),
  expected_close   date,
  status           opportunity_status not null default 'open',
  external_id      text,                                 -- CRM deal id when synced
  notes            text,
  created_at       timestamptz not null default now(),
  updated_at       timestamptz not null default now(),
  deleted_at       timestamptz
);
create index idx_opportunities_workspace_status on opportunities (workspace_id, status) where deleted_at is null;

create table opportunity_contacts (
  opportunity_id uuid not null references opportunities(id) on delete cascade,
  contact_id     uuid not null references contacts(id) on delete cascade,
  role           opportunity_role not null default 'other',
  primary key (opportunity_id, contact_id)
);

create table contact_edges (                              -- contact-to-contact relationships for the network graph
  id            uuid primary key default gen_random_uuid(),
  workspace_id  uuid not null references workspaces(id) on delete cascade,
  contact_a_id  uuid not null references contacts(id) on delete cascade,
  contact_b_id  uuid not null references contacts(id) on delete cascade,
  kind          edge_kind not null default 'knows',
  strength      smallint not null default 50 check (strength between 0 and 100),
  source        text not null default 'manual',
  note          text,
  created_by    uuid not null references profiles(id),
  created_at    timestamptz not null default now(),
  check (contact_a_id < contact_b_id),                   -- canonical ordering; enforce in the API before insert
  unique (workspace_id, contact_a_id, contact_b_id)
);
create index idx_contact_edges_b on contact_edges (contact_b_id);

create table relationship_scores (                         -- daily history for trends
  id           uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references workspaces(id) on delete cascade,
  contact_id   uuid not null references contacts(id) on delete cascade,
  scored_on    date not null,
  score        smallint not null check (score between 0 and 100),
  components   jsonb not null,                            -- {"recency":0.8,"frequency":0.5,"sentiment":0.7,"reciprocity":0.6,"depth":0.4,"momentum":0.5}
  band         text not null check (band in ('strong','steady','weak','drifting')),
  created_at   timestamptz not null default now(),
  unique (contact_id, scored_on)
);
create index idx_relationship_scores_contact on relationship_scores (contact_id, scored_on desc);

create table insights (
  id               uuid primary key default gen_random_uuid(),
  workspace_id     uuid not null references workspaces(id) on delete cascade,
  user_id          uuid references profiles(id) on delete cascade,   -- null = workspace-wide (managers)
  contact_id       uuid references contacts(id) on delete cascade,
  company_id       uuid references companies(id) on delete cascade,
  kind             insight_kind not null,
  severity         insight_severity not null default 'info',
  title            text not null,
  body             text not null,
  evidence         jsonb not null default '{}'::jsonb,   -- rule inputs, numbers, interaction ids
  suggested_action jsonb,                                -- {"type":"create_task","payload":{...}} | {"type":"open_contact"} | {"type":"draft_message"}
  dedupe_key       text not null,                        -- e.g. "at_risk:<contact_id>:2026-09"
  status           insight_status not null default 'new',
  expires_at       timestamptz,
  generated_by     text not null,                        -- "rules:v1" or "rules:v1+llm:<model>"
  created_at       timestamptz not null default now(),
  updated_at       timestamptz not null default now(),
  unique (workspace_id, dedupe_key)
);
create index idx_insights_user_status on insights (user_id, status, created_at desc);
create index idx_insights_workspace_status on insights (workspace_id, status, created_at desc);

create table context_items (                              -- Phase 3 news/context feed
  id            uuid primary key default gen_random_uuid(),
  workspace_id  uuid not null references workspaces(id) on delete cascade,
  contact_id    uuid references contacts(id) on delete cascade,
  company_id    uuid references companies(id) on delete cascade,
  source        text not null,
  url           text not null,
  title         text not null,
  summary       text,
  published_at  timestamptz,
  relevance     real check (relevance between 0 and 1),
  created_at    timestamptz not null default now(),
  unique (workspace_id, url)
);

create table integrations (
  id                   uuid primary key default gen_random_uuid(),
  workspace_id         uuid not null references workspaces(id) on delete cascade,
  user_id              uuid not null references profiles(id) on delete cascade,
  provider             integration_provider not null,
  status               integration_status not null default 'connected',
  external_account_id  text,
  scopes               text[] not null default '{}',
  credentials_enc      bytea,                             -- AES-256-GCM (APP_ENCRYPTION_KEY); never returned by the API
  sync_cursor          jsonb not null default '{}'::jsonb,
  last_synced_at       timestamptz,
  last_error           text,
  created_at           timestamptz not null default now(),
  updated_at           timestamptz not null default now(),
  unique (user_id, provider)
);
```

### 5.5 Operational tables (`0004_ops.sql`)

```sql
create table jobs (
  id            uuid primary key default gen_random_uuid(),
  kind          text not null,                            -- capture.transcribe, capture.extract, profile.synthesize, brief.generate, scores.compute, insights.generate, export.build, integration.sync
  payload       jsonb not null default '{}'::jsonb,
  workspace_id  uuid references workspaces(id) on delete cascade,
  user_id       uuid references profiles(id) on delete set null,
  status        job_status not null default 'queued',
  run_after     timestamptz not null default now(),
  priority      smallint not null default 5,              -- 1 highest
  attempts      smallint not null default 0,
  max_attempts  smallint not null default 5,
  locked_by     text,
  locked_at     timestamptz,
  last_error    text,
  result        jsonb,
  dedupe_key    text,                                     -- optional; unique while queued/running
  created_at    timestamptz not null default now(),
  started_at    timestamptz,
  finished_at   timestamptz
);
create index idx_jobs_claim on jobs (priority, run_after) where status = 'queued';
create unique index idx_jobs_dedupe on jobs (dedupe_key) where status in ('queued', 'running') and dedupe_key is not null;

create table audit_log (
  id             bigint generated always as identity primary key,
  workspace_id   uuid,
  actor_user_id  uuid,
  action         text not null,                            -- contact.create, contact.share, membership.depart, capture.confirm, export.request ...
  entity_type    text,
  entity_id      uuid,
  diff           jsonb,
  ip             inet,
  user_agent     text,
  created_at     timestamptz not null default now()
);
create index idx_audit_workspace_time on audit_log (workspace_id, created_at desc);

create table exports (
  id            uuid primary key default gen_random_uuid(),
  workspace_id  uuid not null references workspaces(id) on delete cascade,
  user_id       uuid not null references profiles(id) on delete cascade,
  scope         text not null check (scope in ('personal', 'my_contributions', 'workspace')),
  status        job_status not null default 'queued',
  storage_path  text,
  expires_at    timestamptz,
  created_at    timestamptz not null default now()
);
```

### 5.6 Triggers and functions (`0005_functions.sql`)

```sql
create or replace function set_updated_at() returns trigger language plpgsql as $$
begin new.updated_at = now(); return new; end $$;
-- attach to every table with updated_at (profiles, workspaces, memberships, companies, contacts, contact_facts,
-- contact_profiles, interactions, captures, tasks, opportunities, insights, integrations)

-- keep contacts.last_interaction_at current and mark the AI profile stale
create or replace function on_interaction_written() returns trigger language plpgsql as $$
begin
  if new.contact_id is not null and new.deleted_at is null then
    update contacts set last_interaction_at = greatest(coalesce(last_interaction_at, 'epoch'), new.occurred_at)
      where id = new.contact_id;
    update contact_profiles set stale = true where contact_id = new.contact_id;
  end if;
  return new;
end $$;
create trigger trg_interaction_written after insert or update of occurred_at, deleted_at on interactions
  for each row execute function on_interaction_written();

create or replace function on_fact_written() returns trigger language plpgsql as $$
begin
  update contact_profiles set stale = true where contact_id = new.contact_id;
  return new;
end $$;
create trigger trg_fact_written after insert or update on contact_facts for each row execute function on_fact_written();

-- ensure a contact_profiles row exists for every contact
create or replace function on_contact_created() returns trigger language plpgsql as $$
begin
  insert into contact_profiles (contact_id, workspace_id) values (new.id, new.workspace_id) on conflict do nothing;
  return new;
end $$;
create trigger trg_contact_created after insert on contacts for each row execute function on_contact_created();

-- fuzzy contact search used by /search and capture contact-matching
create or replace function search_contacts(ws uuid, q text, lim int default 20)
returns table (id uuid, display_name text, title text, company_name text, gravity_score smallint, rank real)
language sql stable as $$
  select c.id, c.display_name, c.title, co.name, c.gravity_score,
         greatest(similarity(c.display_name, q), ts_rank(c.search_vector, plainto_tsquery('simple', q))) as rank
  from contacts c left join companies co on co.id = c.company_id
  where c.workspace_id = ws and c.deleted_at is null
    and (c.display_name % q or c.search_vector @@ plainto_tsquery('simple', q) or co.name ilike '%' || q || '%')
  order by rank desc limit lim
$$;
```

Job enqueueing from the API runs through a `security definer` function so that `authenticated` never needs privileges on `jobs`:

```sql
create or replace function enqueue_job(p_kind text, p_payload jsonb, p_workspace_id uuid, p_run_after timestamptz default now(),
                                       p_priority smallint default 5, p_dedupe_key text default null)
returns uuid language plpgsql security definer set search_path = public as $$
declare job_id uuid;
begin
  if p_workspace_id is not null and not is_member(p_workspace_id, 'member') then
    raise exception 'not a member of workspace %', p_workspace_id using errcode = '42501';
  end if;
  insert into jobs (kind, payload, workspace_id, user_id, run_after, priority, dedupe_key)
  values (p_kind, p_payload, p_workspace_id, auth.uid(), p_run_after, p_priority, p_dedupe_key)
  on conflict (dedupe_key) where status in ('queued', 'running') and dedupe_key is not null do nothing
  returning id into job_id;
  perform pg_notify('gravv_jobs', coalesce(job_id::text, ''));
  return job_id;
end $$;
revoke all on function enqueue_job(text, jsonb, uuid, timestamptz, smallint, text) from public;
grant execute on function enqueue_job(text, jsonb, uuid, timestamptz, smallint, text) to authenticated;
```

Views for read models (`0006_views.sql`), all created `with (security_invoker = true)` so they inherit RLS from base tables: `contact_overview` (contact + company name + open task count + open opportunity value + 30-day score delta), `workspace_metrics` (per workspace: contact_count, active_90d, avg_gravity, pipeline_value, due_count), and `member_directory` (user id, full_name, role_title, avatar_path, role, for members of workspaces the caller belongs to).

### 5.7 Storage buckets (`0007_storage.sql`)

Private buckets `voice-notes`, `exports`, `avatars`. Object paths are `<workspace_id>/<user_id>/<uuid>.<ext>`. Policies on `storage.objects`: a user may read/write objects whose first path segment is a workspace they are an active member of and whose second segment is their own user id; managers and admins may read all objects under their workspace's prefix. The API issues signed upload and download URLs (Section 7.8); the browser never uses the secret key.

### 5.8 Migration workflow

1. `make db-migrate name=<change>` creates `supabase/migrations/<timestamp>_<change>.sql`.
2. Write SQL by hand (never rely on Studio edits; if you experiment in Studio, run `make db-diff` and paste the diff into a migration).
3. `make db-reset` applies everything from scratch and seeds. Reset must succeed from zero on every commit; CI enforces it.
4. Update SQLAlchemy models in `apps/api/app/db/models` to match. The test `tests/integration/test_schema_parity.py` reflects the live schema and asserts every model column exists with a compatible type.
5. Deploy: CI runs `supabase db push` against staging on merge to `main`, and against prod on a release tag, before the new API image is rolled out (migrations must be backward compatible with the previous API version: add columns nullable, backfill, then constrain in a later migration).

---
## 6. Authentication, authorization, user management, security

### 6.1 Authentication (Supabase Auth)

- Methods enabled in `supabase/config.toml` and the hosted dashboard: email + password (with email confirmation in staging/prod, disabled locally), magic link, Google OAuth, Microsoft (Azure) OAuth. TOTP MFA available from Settings > Security (Supabase MFA API); workspaces can require MFA for `manager` and above (`workspaces.settings.require_mfa`).
- The web app uses `supabase-js` for sign-up, sign-in, OAuth redirects, session refresh, password reset, and MFA enrollment. It never calls PostgREST directly in v1; all data goes through the FastAPI API with the Supabase access token as `Authorization: Bearer <jwt>`.
- Session storage: supabase-js default (localStorage) with short-lived access tokens (set JWT expiry to 15 minutes in the dashboard; refresh tokens rotate). Revisit with a cookie-based BFF if the threat model changes (recorded as an open question in Appendix D).
- Password policy: minimum 12 characters, checked against HaveIBeenPwned (Supabase setting). Rate limits on auth endpoints are Supabase defaults.

### 6.2 JWT verification in FastAPI (`app/auth/jwt.py`)

```python
# Behaviour, not final code:
# 1. Read the `alg` and `kid` from the token header without verifying.
# 2. If alg is ES256/RS256: fetch and cache (10 min) JWKS from f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json"
#    using PyJWT's PyJWKClient; verify signature, `exp`, `iat`, `aud == "authenticated"`, and
#    `iss == f"{SUPABASE_URL}/auth/v1"`.
# 3. If alg is HS256 (legacy projects and some local setups): verify with SUPABASE_JWT_SECRET.
# 4. Reject anything else. Return AuthContext(user_id=sub, email, role, session_id, aal, claims).
# 5. `aal` (authenticator assurance level) is exposed so endpoints can require "aal2" (MFA) for admin actions.
```

Dependencies (`app/auth/deps.py`):

- `current_user()` -> `AuthContext` or 401 (`Problem` type `unauthenticated`).
- `current_workspace()` -> reads `X-Workspace-Id` header (falls back to `profiles.default_workspace_id`), verifies active membership, returns `WorkspaceContext(workspace_id, role)`; 403 `not_a_member` otherwise.
- `require_role(min_role)` -> 403 `insufficient_role`. Role order: viewer < member < manager < admin < owner.
- `require_mfa()` -> 403 `mfa_required` when `aal != "aal2"` and the workspace requires MFA.

### 6.3 Authorization matrix

| Capability | viewer | member | manager | admin | owner |
| --- | --- | --- | --- | --- | --- |
| Read team-visible contacts, interactions, tasks, opportunities | yes | yes | yes | yes | yes |
| Create/edit own contacts, interactions, facts, tasks, captures | no | yes | yes | yes | yes |
| Edit contacts owned by others | no | no | yes | yes | yes |
| Delete/archive contacts owned by others | no | no | no | yes | yes |
| View private contacts of others | no | no | no | no | no |
| Team analytics (per-member metrics, enterprise dashboard) | no | no | yes | yes | yes |
| Invite members, change roles below own | no | no | no | yes | yes |
| Remove members / mark departed | no | no | no | yes | yes |
| Workspace settings, integrations at workspace level | no | no | no | yes | yes |
| Transfer ownership, delete workspace, billing | no | no | no | no | yes |
| Export "my contributions" | yes | yes | yes | yes | yes |
| Export whole workspace | no | no | no | yes | yes |

Personal workspaces have exactly one membership (owner). All contacts there are `private`.

### 6.4 Row Level Security (the enforcement layer)

RLS is on for every table in `public`. The API does not bypass it. Helpers (`0008_rls.sql`):

```sql
-- role ranking for comparisons
create or replace function role_rank(r workspace_role) returns int language sql immutable as $$
  select case r when 'viewer' then 1 when 'member' then 2 when 'manager' then 3 when 'admin' then 4 when 'owner' then 5 end $$;

-- membership check that does not recurse into memberships' own policies
create or replace function is_member(ws uuid, min_role workspace_role default 'viewer')
returns boolean language sql stable security definer set search_path = public as $$
  select exists (
    select 1 from memberships m
    where m.workspace_id = ws and m.user_id = auth.uid() and m.status = 'active'
      and role_rank(m.role) >= role_rank(min_role))
$$;
revoke all on function is_member(uuid, workspace_role) from public;
grant execute on function is_member(uuid, workspace_role) to authenticated;
```

Policy pattern (shown for `contacts`; replicate with the same shape for every table):

```sql
alter table contacts enable row level security;

create policy contacts_select on contacts for select to authenticated using (
  deleted_at is null
  and is_member(workspace_id, 'viewer')
  and (visibility = 'team' or owner_user_id = auth.uid())
);
create policy contacts_insert on contacts for insert to authenticated with check (
  is_member(workspace_id, 'member') and owner_user_id = auth.uid()
);
create policy contacts_update on contacts for update to authenticated using (
  is_member(workspace_id, 'member')
  and (owner_user_id = auth.uid() or is_member(workspace_id, 'manager'))
) with check (
  is_member(workspace_id, 'member')
);
create policy contacts_delete on contacts for delete to authenticated using (
  owner_user_id = auth.uid() or is_member(workspace_id, 'admin')
);
```

Table-specific rules:

- `profiles`: a user reads and updates only their own row; other members' `full_name`, `role_title`, `avatar_path` are exposed through a `member_directory` view scoped by shared workspace.
- `memberships`: select where `user_id = auth.uid()` or `is_member(workspace_id, 'member')`; insert/update/delete only `is_member(workspace_id, 'admin')`, plus a user may update their own row to `departed`.
- `workspaces`: select where `is_member(id)`; update `is_member(id, 'admin')`; delete owner only; insert any authenticated user (creating an organization) with `owner_user_id = auth.uid()`.
- `invitations`: admins of the workspace; acceptance happens in the API using the worker role after validating the token hash and matching the email.
- Child tables (`contact_facts`, `interactions`, `tasks`, `contact_edges`, `relationship_scores`, `insights`, `captures`, `opportunities`): membership via `workspace_id`, and visibility follows the parent contact (`exists (select 1 from contacts c where c.id = contact_id)` re-uses the contact policy).
- `jobs`, `audit_log`, `exports`: no policies for `authenticated` (deny all); only the worker role reads and writes them. The API enqueues jobs through a `security definer` function `enqueue_job(kind, payload, workspace_id, user_id, run_after, dedupe_key)` that validates membership.
- `integrations`: user's own rows; `credentials_enc` column is revoked from `authenticated` entirely (`revoke select (credentials_enc) on integrations from authenticated`) so it cannot leak even through a bug.

Grants:

```sql
revoke all on all tables in schema public from anon;
grant usage on schema public to authenticated;
grant select, insert, update, delete on all tables in schema public to authenticated;
alter default privileges in schema public grant select, insert, update, delete on tables to authenticated;
```

### 6.5 Database roles and how the API binds identity

Migration `0009_roles.sql` creates two `nologin` roles; `infra/scripts/setup_roles.sh` sets passwords per environment (passwords never live in migrations):

```sql
create role gravv_api nologin;      grant authenticated to gravv_api;
create role gravv_worker nologin;   grant service_role to gravv_worker;
```

Per request, the API opens a transaction and binds the caller's identity so that `auth.uid()` and every policy work exactly as they would through PostgREST:

```python
async with session.begin():
    await session.execute(text("set local role authenticated"))
    await session.execute(text("select set_config('request.jwt.claims', :claims, true)"),
                          {"claims": json.dumps({"sub": ctx.user_id, "role": "authenticated",
                                                 "email": ctx.email, "aal": ctx.aal})})
    yield session
```

Rules:

- One transaction per request; the `set local` calls are the first statements. Read-only endpoints still use a transaction (required for `set local`).
- Production connects through Supavisor in transaction mode (port 6543). Therefore: `asyncpg` with `statement_cache_size=0`, no session-level state, no `LISTEN` on the API pool.
- The worker connects with `gravv_worker` and never sets a user identity except when a job acts on behalf of a user, in which case it uses the same binding as the API with that user's id (jobs store `user_id`). Cross-tenant jobs (nightly scoring) run as the worker role and are the only code allowed to read across workspaces; each such handler filters by `workspace_id` explicitly and is listed in `docs/DECISIONS.md`.
- Never use the `postgres` role from application code.

### 6.6 User management flows

- Sign-up: Supabase creates `auth.users`; trigger provisions profile, personal workspace, membership. First login routes to `/onboarding` until `profiles.onboarding_step = 5`.
- Onboarding (mirrors the mockup, five steps): 1) name, role title, timezone; 2) professional and personal interests (tag picker + custom); 3) goals (four checkboxes + free text); 4) integrations (cards; Google and Microsoft show "Connect" and start OAuth in Phase 3, others show "Available soon"; "Skip for now" always available); 5) done, with a plain list of what happens next. Each step is a `PATCH /me/onboarding` call so progress survives reloads.
- Create organization: any user; becomes owner; can set slug, default contact visibility, default cadence.
- Invite: admin enters email and role; API stores `sha256(token)`, emails the raw token link (Supabase Auth invite for new users, plain email through Supabase's SMTP for existing users; local: Mailpit). Accept: signed-in user with matching email hits `POST /invitations/{token}/accept`; membership becomes `active`.
- Role change: admins may set roles strictly below their own; owner may transfer ownership (requires MFA `aal2`).
- Departure: admin marks membership `departed` (`departed_at = now()`, `grace_until = now() + 30 days`) or the member leaves. Access to the workspace ends immediately (policies check `status = 'active'`). An export of the departing user's contributions is enqueued automatically and emailed. Personal workspace is untouched.
- Account deletion: `DELETE /me` requires re-authentication (fresh token < 5 minutes) and MFA if enrolled; deletes `auth.users` (cascades personal data); organization-owned records keep `created_by` pointing at a tombstone profile (`profiles.deleted_at`, name replaced with "Former member").

### 6.7 Security controls checklist (implement in M7, verify in CI where possible)

- Transport: HTTPS everywhere (App Runner and CloudFront provide TLS); HSTS via CloudFront response headers policy.
- Headers on API responses: `Cache-Control: no-store` for authenticated routes, `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`. SPA CSP set at CloudFront: `default-src 'self'; connect-src 'self' https://<api-domain> https://<project>.supabase.co; img-src 'self' data: blob: https://<project>.supabase.co; media-src blob: https://<project>.supabase.co; font-src 'self'; style-src 'self' 'unsafe-inline'; frame-ancestors 'none'`.
- CORS: explicit allowlist from `CORS_ORIGINS`; no wildcard.
- Input validation: Pydantic schemas with length limits on every text field; array limits (max 50 tags, 20 emails); reject unknown fields (`extra="forbid"`).
- Rate limiting: per-user token bucket in the API (`slowapi` or a small middleware keyed by `sub`, backed by an in-memory store per instance; acceptable at App Runner scale, revisit in Section 14). Stricter limits on `/capture/*` and `/ai/*` routes (LLM cost).
- File uploads: audio only (`audio/webm`, `audio/mp4`, `audio/mpeg`, `audio/wav`), max 25 MB, max 10 minutes; verified by content sniffing in the worker before transcription.
- Secrets: AWS SSM Parameter Store (SecureString) injected as App Runner secrets; never in images or repo. `APP_ENCRYPTION_KEY` rotates with a two-key window (current + previous) supported by `app/crypto.py`.
- Credential encryption: AES-256-GCM with a per-row random nonce; associated data = `integrations.id`.
- Audit: every mutation on contacts, memberships, workspaces, exports, integrations, and capture confirmations writes `audit_log` (via the worker role in an `after commit` hook queued through `enqueue_job('audit.write')` to keep it out of the user transaction, or directly with a `security definer` function; choose the function for simplicity).
- AI safety: notes and transcripts are untrusted text; prompts wrap them in delimiters, instruct the model to treat them as data, and use structured outputs; extracted actions are proposals; the model has no tools that reach the database or the network.
- Logging: no request bodies, no transcripts, no tokens in logs; user ids and workspace ids only.
- Dependency hygiene: `pip-audit` and `pnpm audit` in CI (non-blocking at first, blocking for high severity after M7); Dependabot enabled.
- Backups: Supabase daily backups (Pro plan) plus PITR add-on for prod; quarterly restore drill documented in `docs/RUNBOOK.md`.
- Privacy: data export and account deletion endpoints exist from M6; retention: soft-deleted rows purged after 30 days by a worker job; audio files purged 30 days after confirmation unless the workspace setting `retain_audio` is true.

---

## 7. Backend (FastAPI) architecture

### 7.1 Application structure

- `app/main.py` builds the app: CORS, request-id middleware, structured logging, rate limiting, exception handlers producing RFC 9457 Problem Details, routers mounted under `/api/v1`, `/healthz` (process alive) and `/readyz` (DB reachable, migrations at expected version).
- Each domain package has `router.py` (HTTP only), `schemas.py` (Pydantic in/out), `service.py` (business logic, transaction boundaries), and uses `db/repositories` for SQL. Routers never contain SQL. Services never import FastAPI.
- `app/config.py` uses `pydantic-settings`; `APP_ENV=test` forces `LLM_PROVIDER=fake` and `TRANSCRIPTION_PROVIDER=fake`.

### 7.2 Request lifecycle

1. Middleware assigns `X-Request-Id` (or propagates it), starts a timer, binds request id and user id into structlog context.
2. `current_user` verifies the JWT.
3. `current_workspace` resolves the workspace and role.
4. `get_session` opens the RLS-bound transaction (Section 6.5).
5. Router validates input, calls the service, service returns domain objects, router maps to response schema.
6. Commit on success; on any exception the transaction rolls back, and the handler returns a Problem response with the request id.

### 7.3 Error format

All errors are `application/problem+json`:

```json
{ "type": "https://gravv.app/problems/insufficient_role", "title": "Insufficient role", "status": 403,
  "detail": "This action requires the manager role or higher.", "instance": "/api/v1/contacts/...", "request_id": "..." }
```

Validation errors include `errors: [{ "field": "emails.0", "message": "..." }]`. Never leak stack traces.

### 7.4 Pagination, filtering, sorting

- Cursor pagination on every list endpoint: `?limit=25&cursor=<opaque>`; response `{ "items": [...], "next_cursor": "..." | null }`. Cursors encode `(sort_value, id)` base64url; default sort `updated_at desc`.
- Filters are explicit query params (documented per endpoint); no generic query language.
- Sorting whitelist per endpoint.

### 7.5 OpenAPI and client generation

- Every route has `operation_id` set explicitly (`contacts_list`, `contacts_get`, ...) so generated client names are stable.
- `make gen` runs the app in `APP_ENV=test`, dumps `openapi.json`, and runs `openapi-typescript` into `apps/web/src/lib/api/schema.d.ts`. CI fails if the generated file is out of date.

### 7.6 Jobs and worker (Postgres queue)

Claim query (single statement, safe with many workers):

```sql
with next as (
  select id from jobs
  where status = 'queued' and run_after <= now()
  order by priority, run_after
  for update skip locked
  limit 1
)
update jobs j set status = 'running', locked_by = :worker_id, locked_at = now(), started_at = coalesce(started_at, now()),
                  attempts = attempts + 1
from next where j.id = next.id
returning j.*;
```

- Handlers are async functions registered by `kind` in `app/jobs/handlers/__init__.py`. Each handler receives `(job, worker_session_factory)` and is idempotent (re-running after a crash must not duplicate facts, tasks, or interactions; use `dedupe_key`s and upserts).
- Completion: `succeeded` with `result`; failure: `failed` with `last_error`, `run_after = now() + backoff(attempts)` (30s, 2m, 10m, 1h, 6h), status back to `queued` while `attempts < max_attempts`, else `dead`. A dead job raises an alarm (Section 13.7).
- Stale lock reaper: jobs `running` for more than 15 minutes with a `locked_at` older than that are re-queued (workers heartbeat `locked_at` every 60 s for long transcriptions).
- Scheduler (`app/jobs/scheduler.py`, runs inside the worker with a leader lock via `pg_advisory_lock`): enqueues `scores.compute` for every workspace daily at 02:00 UTC, `insights.generate` at 02:30 UTC, `retention.purge` weekly, `profile.synthesize` for stale profiles hourly (batched, max 50 per run per workspace), `integration.sync` every 15 minutes per connected integration (Phase 3).
- Wake-up: workers poll every `WORKER_POLL_INTERVAL_SECONDS`; the API additionally `NOTIFY gravv_jobs` after enqueue and the worker `LISTEN`s (worker has a dedicated session-mode connection, port 5432) so captures start within a second.
- Local: `make dev` runs one worker; tests run handlers inline via `run_job_now(job_id)`.

### 7.7 AI layer (`app/ai`)

```python
class LLMClient(Protocol):
    async def complete_structured(self, *, prompt: Prompt, schema: type[BaseModel], max_tokens: int) -> BaseModel: ...
    async def complete_text(self, *, prompt: Prompt, max_tokens: int) -> str: ...

class TranscriptionClient(Protocol):
    async def transcribe(self, *, audio: bytes, mime: str, language: str | None) -> Transcript: ...
```

- `AnthropicLLM` uses tool-use (a single tool whose input schema is the Pydantic JSON schema) to force structured output; retries once on schema validation failure with the validation error appended.
- `OpenAICompatibleLLM` uses JSON schema response format; kept for provider redundancy.
- `FakeLLM` returns fixtures from `tests/fixtures/ai/<prompt_name>/<case>.json`, selected by a hash of the input, so tests and local dev are deterministic.
- Prompts are versioned files under `app/ai/prompts/<name>/v1.md` with a `{{ }}` template; `prompt_version` is stored on generated artifacts.
- Cost controls: per-workspace daily token budget (`workspaces.settings.ai_daily_token_budget`, default 500k), measured from provider usage fields, enforced by the worker before calling.

### 7.8 Storage (`app/storage.py`)

- `create_signed_upload_url(bucket, path, content_type, max_bytes)` and `create_signed_download_url(bucket, path, ttl)` via Supabase Storage API using the secret key on the server.
- Paths always `<workspace_id>/<user_id>/<uuid>.<ext>`; the API computes the path, the client never chooses it.

### 7.9 Scoring engine (`app/scoring/gravity.py`)

Deterministic and unit-tested with table-driven cases. Inputs for a contact: interactions in the last 180 days (kind, occurred_at, direction, sentiment_score), active fact count, open tasks (overdue count), open opportunities (count, value), `cadence_days`.

```
recency     = exp(-ln(2) * days_since_last / cadence_days)               # half-life = cadence
frequency   = clamp(interactions_last_90d / (90 / cadence_days), 0, 1.5) / 1.5
sentiment   = (mean(sentiment_score of last 10 interactions, default 0) + 1) / 2
reciprocity = 1 - abs(0.5 - inbound_share)*2 (over last 20 interactions; 0.5 = balanced), default 0.5 if < 3 interactions
depth       = min(active_facts, 10) / 10 * 0.7 + (1 if communication_style known else 0) * 0.3
momentum    = 0.5 + 0.25 * sign(score_30d_delta) * min(abs(score_30d_delta)/20, 1) - 0.25 * min(overdue_tasks, 2)/2, clamped 0..1

score = round(100 * (0.35*recency + 0.20*frequency + 0.15*sentiment + 0.10*reciprocity + 0.10*depth + 0.10*momentum))
band  = drifting if days_since_last > 2*cadence_days else strong if score >= 70 else steady if score >= 40 else weak
status (auto, unless archived):
  needs_attention if band in (weak, drifting) or score_30d_delta <= -10
  follow_up       if any open task overdue or due within 3 days, or days_since_last >= cadence_days
  active          otherwise
next_due_at = min(earliest open task due_at, last_interaction_at + cadence_days)
```

Results are written to `relationship_scores` (one row per contact per day, upsert) and denormalized onto `contacts` (`gravity_score`, `status`, `next_due_at`, `gravity_updated_at`). The score of a contact is also recomputed immediately (in the request) after a confirmed capture or a new interaction so the UI reflects it without waiting for the nightly job.

### 7.10 Insight rules (`app/scoring/rules.py`)

Rules detect; the LLM only narrates (optional, workspace setting `insights.narrate_with_llm`). Each rule returns zero or more `InsightDraft(kind, severity, contact_id?, company_id?, title, body, evidence, suggested_action, dedupe_key, expires_at)`.

| Rule | Condition | Suggested action |
| --- | --- | --- |
| `follow_up_due` | `next_due_at` within 3 days or past, no open follow-up task | create_task |
| `at_risk` | band moved to weak/drifting in the last 7 days, or score delta <= -10 over 30 days | create_task, open_contact |
| `opportunity_signal` | 3+ contacts at the same company with interactions in the last 14 days and rising scores | open_company |
| `introduction_path` | target company has no contact with score >= 40 but a strong contact (>= 70) has an edge to someone there | draft_message |
| `common_ground` | new fact matches one of the user's interests (citext equality or LLM-judged similarity when enabled) | open_contact |
| `trend` | monthly avg gravity changed by >= 10% for a company or industry | open_analytics |
| `briefing` | a calendar event with a matched contact in the next 24 h (Phase 3) or an explicit request | open_brief |

Dedupe keys stop repeats (`kind:contact:YYYY-WW`); insights expire after 14 days unless acted on.

---

## 8. API specification (v1)

Base path `/api/v1`. All routes require `Authorization: Bearer <supabase jwt>` except `/healthz`, `/readyz`, and `/invitations/{token}` (GET metadata only). Workspace-scoped routes read `X-Workspace-Id`.

### 8.1 Endpoint index

| Method | Path | operation_id | Role | Notes |
| --- | --- | --- | --- | --- |
| GET | /me | me_get | any | profile + memberships + default workspace |
| PATCH | /me | me_update | any | name, role_title, timezone, goals |
| PATCH | /me/onboarding | me_onboarding_update | any | `{step, data}`; persists interests/goals per step |
| POST | /me/export | me_export | any | scope personal or my_contributions; returns job id |
| DELETE | /me | me_delete | any | requires fresh token (+MFA if enrolled) |
| GET | /workspaces | workspaces_list | any | memberships with roles |
| POST | /workspaces | workspaces_create | any | organization |
| GET | /workspaces/{id} | workspaces_get | viewer | |
| PATCH | /workspaces/{id} | workspaces_update | admin | name, slug, settings |
| GET | /workspaces/{id}/members | members_list | member | |
| PATCH | /workspaces/{id}/members/{user_id} | members_update | admin | role, status=departed |
| DELETE | /workspaces/{id}/members/me | members_leave | member | self-departure |
| POST | /workspaces/{id}/invitations | invitations_create | admin | |
| GET | /workspaces/{id}/invitations | invitations_list | admin | |
| DELETE | /workspaces/{id}/invitations/{inv_id} | invitations_revoke | admin | |
| GET | /invitations/{token} | invitations_peek | public | workspace name, role, inviter |
| POST | /invitations/{token}/accept | invitations_accept | any | email must match |
| GET | /companies | companies_list | viewer | q, type, industry |
| POST | /companies | companies_create | member | |
| GET/PATCH/DELETE | /companies/{id} | companies_get/update/delete | viewer/member/admin | |
| GET | /contacts | contacts_list | viewer | q, status, band, company_id, relationship_type, tag, owner=me, sort one of gravity, last_interaction, name, next_due |
| POST | /contacts | contacts_create | member | |
| GET | /contacts/{id} | contacts_get | viewer | overview: contact, company, profile, counts, score delta |
| PATCH | /contacts/{id} | contacts_update | member (own) / manager | |
| DELETE | /contacts/{id} | contacts_delete | owner-of-record / admin | soft delete |
| POST | /contacts/{id}/share | contacts_share | member | `{target_workspace_id}` copy from personal to org |
| POST | /contacts/{id}/copy-to-personal | contacts_copy_to_personal | member | only for contacts the caller created |
| GET | /contacts/{id}/timeline | contacts_timeline | viewer | cursor; kinds filter; merges interactions + tasks completed + score changes |
| GET | /contacts/{id}/facts | facts_list | viewer | active only unless `include_inactive` |
| POST | /contacts/{id}/facts | facts_create | member | |
| PATCH | /facts/{id} | facts_update | member | editing creates a superseding fact |
| DELETE | /facts/{id} | facts_delete | member | deactivates |
| GET | /contacts/{id}/profile | profile_get | viewer | synthesized profile + stale flag |
| POST | /contacts/{id}/profile/regenerate | profile_regenerate | member | enqueues profile.synthesize; 202 + job |
| POST | /contacts/{id}/brief | brief_create | member | enqueues brief.generate; 202 + job |
| GET | /contacts/{id}/scores | scores_history | viewer | `range` one of 30d, 90d, 1y |
| GET | /contacts/{id}/edges | edges_list | viewer | |
| POST | /contacts/{id}/edges | edges_create | member | `{other_contact_id, kind, strength, note}` |
| DELETE | /edges/{id} | edges_delete | member | |
| GET | /interactions | interactions_list | viewer | contact_id, kind, since, until |
| POST | /interactions | interactions_create | member | manual note/meeting/call; `extract=true` enqueues capture.extract |
| PATCH/DELETE | /interactions/{id} | interactions_update/delete | member (own) / manager | |
| POST | /captures/text | captures_create_text | member | `{text, contact_id?, idempotency_key}` -> 202 capture |
| POST | /captures/voice/upload-url | captures_voice_upload_url | member | `{content_type, size_bytes, contact_id?, idempotency_key}` -> `{capture_id, upload_url, storage_path}` |
| POST | /captures/{id}/uploaded | captures_voice_uploaded | member | client confirms upload; enqueues transcribe |
| GET | /captures/{id} | captures_get | member (own) | status, transcript, proposal |
| POST | /captures/{id}/confirm | captures_confirm | member (own) | edited proposal -> interaction, facts, tasks, edges |
| POST | /captures/{id}/discard | captures_discard | member (own) | |
| GET | /captures | captures_list | member | own pending proposals |
| GET | /tasks | tasks_list | viewer | status, due_before, contact_id, assignee=me |
| POST | /tasks | tasks_create | member | |
| PATCH | /tasks/{id} | tasks_update | member | |
| POST | /tasks/{id}/complete | tasks_complete | member | |
| POST | /tasks/{id}/snooze | tasks_snooze | member | `{until}` |
| GET | /opportunities | opportunities_list | viewer | status, company_id, owner=me |
| POST | /opportunities | opportunities_create | member | |
| GET/PATCH/DELETE | /opportunities/{id} | opportunities_get/update/delete | | |
| PUT | /opportunities/{id}/contacts/{contact_id} | opportunity_contacts_put | member | `{role}` |
| DELETE | /opportunities/{id}/contacts/{contact_id} | opportunity_contacts_delete | member | |
| GET | /insights | insights_list | viewer | status=new, kind, contact_id, scope one of me, team (team requires manager+) |
| POST | /insights/{id}/status | insights_set_status | viewer | seen, acted, dismissed |
| POST | /insights/{id}/act | insights_act | member | executes suggested_action (e.g. creates the task) |
| POST | /insights/generate | insights_generate_now | manager | enqueues insights.generate for the workspace (rate limited 1/10min) |
| GET | /analytics/summary | analytics_summary | viewer | `range` one of today, week, month, quarter, year; scope one of me (default), team (manager+) |
| GET | /analytics/distribution | analytics_distribution | viewer | counts per band |
| GET | /analytics/interactions | analytics_interactions | viewer | series per period, per kind |
| GET | /analytics/top-contacts | analytics_top_contacts | viewer | table rows |
| GET | /analytics/team | analytics_team | manager | per-member metrics |
| GET | /network/graph | network_graph | viewer | filters: relationship_type, industry, min_score; returns nodes and edges (Section 9.7) |
| GET | /network/paths | network_paths | viewer | `from` is me or a contact id; `to` is a contact id or company id; shortest paths (max 4 hops, top 3) |
| GET | /search | search_global | viewer | `q`; contacts, companies, interactions (top 5 each) |
| GET | /integrations | integrations_list | member | status only |
| POST | /integrations/{provider}/connect | integrations_connect | member | returns OAuth URL (Phase 3) |
| GET | /integrations/{provider}/callback | integrations_callback | member | Phase 3 |
| DELETE | /integrations/{provider} | integrations_disconnect | member | |
| POST | /integrations/{provider}/sync | integrations_sync | member | Phase 3 |
| GET | /jobs/{id} | jobs_get | any (own) | status, result, error (sanitized) |
| GET | /exports/{id} | exports_get | any (own) | signed download URL when ready |
| GET | /healthz, /readyz | health_live, health_ready | public | |

### 8.2 Key schemas (Pydantic, mirrored in the generated TS client)

```python
class ContactCreate(BaseModel, extra="forbid"):
    first_name: str = Field(min_length=1, max_length=80)
    last_name: str = Field(default="", max_length=80)
    honorific: str | None = Field(default=None, max_length=20)
    title: str | None = Field(default=None, max_length=120)
    company_id: UUID | None = None
    company_name: str | None = Field(default=None, max_length=120)   # creates/links a company by name
    emails: list[EmailStr] = Field(default_factory=list, max_length=20)
    phones: list[str] = Field(default_factory=list, max_length=20)
    location: str | None = None
    relationship_type: RelationshipType = "other"
    visibility: ContactVisibility | None = None                      # default from workspace settings
    tags: list[str] = Field(default_factory=list, max_length=50)
    cadence_days: int = Field(default=30, ge=1, le=365)

class ContactRead(BaseModel):
    id: UUID; workspace_id: UUID; owner_user_id: UUID
    display_name: str; honorific: str | None; first_name: str; last_name: str; title: str | None
    company: CompanySummary | None
    emails: list[str]; phones: list[str]; location: str | None
    relationship_type: RelationshipType; visibility: ContactVisibility; status: ContactStatus; tags: list[str]
    cadence_days: int; gravity_score: int; band: Band; score_delta_30d: int | None
    last_interaction: InteractionSummary | None; next_due_at: datetime | None
    open_task_count: int; open_opportunity_value_cents: int
    profile: ContactProfileRead | None
    created_at: datetime; updated_at: datetime

class CaptureExtraction(BaseModel):                                  # produced by the LLM, edited by the user, applied on confirm
    contact_match: ContactMatch | None                              # {contact_id, display_name, confidence} or null
    interaction: ExtractedInteraction                               # {kind, occurred_at?, subject, summary, body, sentiment, sentiment_score, direction}
    facts: list[ExtractedFact]                                      # {category, content, confidence}
    tasks: list[ExtractedTask]                                      # {title, due_at?, priority, contact_ref?}
    mentioned_people: list[MentionedPerson]                         # {name, title?, company?, relationship_hint?}
    mentioned_companies: list[str]
    edges: list[ExtractedEdge]                                      # {person_a, person_b, kind}
    needs_review: list[str]                                         # model's own uncertainty notes, shown to the user

class CaptureConfirm(BaseModel, extra="forbid"):
    contact_id: UUID
    interaction: ExtractedInteraction
    facts: list[ExtractedFact]
    tasks: list[ExtractedTask]
    edges: list[ExtractedEdge]
    create_contacts_for: list[MentionedPerson]                      # people the user wants added as new contacts

class AnalyticsSummary(BaseModel):
    range: str; scope: Literal["me", "team"]
    contact_count: int; contact_count_delta: int
    active_count: int; engagement_rate: float
    avg_gravity: int; avg_gravity_delta: int
    pipeline_value_cents: int; pipeline_delta_pct: float; open_opportunity_count: int
    due_count: int
```

### 8.3 Capture flow contract (the tap-to-talk path)

1. `POST /captures/voice/upload-url` -> API creates `captures` row (`uploaded`), returns a signed PUT URL valid 5 minutes.
2. Client uploads the blob directly to Supabase Storage.
3. `POST /captures/{id}/uploaded` -> API verifies the object exists (HEAD via storage API), enqueues `capture.transcribe` (priority 1).
4. Worker transcribes, stores `transcript`, sets `transcribed`, chains `capture.extract`.
5. `capture.extract` builds the prompt with: transcript, the user's contacts matching names in the text (top 10 from `search_contacts` on capitalized tokens), the selected contact's existing facts (to avoid duplicates), current date and timezone. Stores `proposal`, sets `proposed`.
6. Client polls `GET /captures/{id}` (2 s while pending; TanStack Query `refetchInterval`) and renders the proposal editor: pick or confirm contact, edit interaction summary, toggle facts, edit tasks, choose which mentioned people become contacts.
7. `POST /captures/{id}/confirm` applies everything in one transaction: interaction (with `ai_extraction` and `ai_status=processed`), facts (skip duplicates by case-insensitive content per contact), tasks, edges, new contacts; recomputes the contact's score; enqueues `profile.synthesize`; writes audit. Returns the created interaction and updated contact.
8. Text captures skip steps 1-4 (`POST /captures/text` goes straight to `extracting`).

Idempotency: clients send a UUID `idempotency_key`; a repeated request returns the existing capture.

---
## 9. Frontend architecture (apps/web)

### 9.1 Stack and structure

- React + TypeScript + Vite; `strict` TS; path alias `@/`.
- Routing: React Router (data routers, lazy route modules per feature).
- Server state: TanStack Query. Client state: Zustand only for UI (active workspace id, capture sheet open, theme).
- Forms: react-hook-form + zod schemas derived from the generated OpenAPI types (`zod` schemas live next to the form; keep them in sync with the API's Pydantic limits).
- Styling: Tailwind v4 with all tokens defined once in `src/design/tokens.css` (`@theme`). Components use Tailwind utilities that reference tokens; no arbitrary values (`bg-[#123456]` is forbidden and linted by a custom ESLint rule / grep in CI).
- Icons: `lucide-react` wrapped by `<Icon name>` which sets `strokeWidth=1.75`, `strokeLinecap="square"`, `strokeLinejoin="miter"` (angular icons that match the edges). No other icon source, no emoji.
- Charts: Recharts with a shared theme object; network graph: `d3-force`, `d3-zoom`, `d3-quadtree` on a `<canvas>`.
- PWA: `vite-plugin-pwa` (Workbox). Installable, offline app shell, runtime caching for GET API calls (`NetworkFirst`, 5 min), background sync queue for capture uploads in Phase 2.
- API client: `openapi-fetch` over the generated `schema.d.ts`; a middleware injects `Authorization` from the Supabase session and `X-Workspace-Id` from the store; 401 triggers a session refresh then retry once, then sign-out.

### 9.2 Route map

| Path | Screen | Guard |
| --- | --- | --- |
| `/` | Landing (static marketing page, M7) | public |
| `/auth/sign-in`, `/auth/sign-up`, `/auth/magic-link`, `/auth/reset`, `/auth/callback` | Auth screens (supabase-js) | public |
| `/invite/:token` | Invitation preview and accept | public -> requires sign-in to accept |
| `/onboarding` | Five-step wizard | signed in, `onboarding_step < 5` |
| `/app` | redirects to `/app/home` | signed in, onboarded |
| `/app/home` | Home dashboard | |
| `/app/contacts` | Contacts list (search, filters, sort) | |
| `/app/contacts/new` | Create contact | member |
| `/app/contacts/:id` | Contact detail: tabs `overview`, `history`, `notes` (facts), `tasks`, `deals` | |
| `/app/capture` (route-less sheet) | Capture sheet, opened from the dock button anywhere in `/app` | member |
| `/app/captures/:id` | Proposal review (also reachable from "Pending captures") | member |
| `/app/insights` | Insights list | |
| `/app/tasks` | Tasks (due, overdue, done) | |
| `/app/deals` | Opportunities | |
| `/app/network` | Network graph | |
| `/app/analytics` | Analytics; `?scope=team` tab for manager+ | |
| `/app/settings/profile`, `/workspace`, `/members`, `/integrations`, `/security`, `/data` | Settings | role-gated per tab |

Workspace switching: top bar menu; changes `X-Workspace-Id`, invalidates all queries.

### 9.3 App shell

Mobile (< 768px): top bar (workspace name, search, notifications count), scrolling content, bottom dock with four destinations (Home, Contacts, Network, Analytics) and the capture button docked above it at the right. Desktop (>= 768px): left rail 240px with the same destinations plus Insights, Tasks, Deals, Settings; capture button at the bottom of the rail; content max-width 1280px.

```
Mobile                                 Desktop
+----------------------------------+   +--------+----------------------------------------+
| Meridian Components   [search] o |   | Gravv  |  Meridian Components         [search] o |
+----------------------------------+   |        +----------------------------------------+
|                                  |   | Home   |                                        |
|  content                         |   | Contac |  content (max 1280)                    |
|                                  |   | Networ |                                        |
|                             [+]  |   | Analyt |                                        |
+----------------------------------+   | Insigh |                                        |
| Home | Contacts | Network | Anal |   | Tasks  |                                        |
+----------------------------------+   | Deals  |                                        |
                                       | ------ |                                        |
                                       | [Capture]                                       |
                                       | Settin |                                        |
                                       +--------+----------------------------------------+
```

### 9.4 Screens (what each must contain; wireframes are left-aligned, 8px grid)

Home (`/app/home`), from the mobile mockup:

```
Good afternoon, Sarah.                     (greeting in display face; no hamon anywhere else)
------------------------------------------ (the hamon divider: single use in the product)
  247        72         12        $8.2M
  Contacts   Avg gravity  Due this week  Pipeline
------------------------------------------
Due next                                       See all
  Col. Michael Johnson   Space Force, Program Director   85  |  cadence due in 2 days
  Sarah Martinez         Lockheed Martin, VP Sales       72  |  overdue 9 days
Recent                                         See all
  Emily Rodriguez        Boeing, Contract Manager        91  |  1d ago
Insights                                       See all
  Follow up with Sarah Martinez   Gravity dropped 15 points in 30 days   [Create task]
  Boeing activity rising          5 contacts active this month           [Open company]
Pending captures (only when non-empty)
  Voice note, 2 min ago, needs review                                    [Review]
```

Contacts list: search field (fuzzy via `/contacts?q=`), filter chips (status, band, relationship type, company, mine), sort menu, dense rows (avatar, name, company and title on the second line, score blade at right with number, next due). Empty state: "No contacts yet. Add one or capture a note about someone." with one primary action.

Contact detail (`/app/contacts/:id`), from the mobile mockup's Overview/History/Notes:

```
<- Contacts
[MJ]  Col. Michael Johnson                                   Gravity 85  strong
      Space Force, Program Director                          [Call] [Email] [Schedule] [Capture note]
      ===============================================----   (score blade, fills once on open)
Overview | History | Notes to remember | Tasks | Deals
Overview:
  Summary (AI, regenerated when stale; shows "Updated 3h ago")
  Style: direct and formal
  Remember: Diet Coke; North Carolina BBQ; competitive pinball
  Last interaction: email, 3 hours ago
  Next due: cadence in 2 days
  Open deal: Phase 2 Satellite Program, $2.5M
  Risks: none recorded
  Common ground with you: none yet
History: timeline (interactions, completed tasks, score changes), filter by kind, infinite scroll.
Notes to remember: facts grouped by category with source badge (manual, voice, note, AI) and "since <date>";
  add fact inline; edit creates a superseding fact; deactivated facts under "Show archived".
Tasks: open/overdue/done with complete and snooze. Deals: linked opportunities with role.
```

Capture sheet (bottom sheet on mobile, right panel on desktop): two modes, Voice (large square button: tap to start, tap to stop; elapsed time; level meter drawn as vertical bars; "Discard" and "Use recording") and Text (textarea with contact picker). Optional contact pre-selected when opened from a contact page. After submit, navigates to the proposal review.

Proposal review (`/app/captures/:id`):

```
Transcript (read-only, expandable)
Contact: [Col. Michael Johnson  (matched, 92%)]  [Change]
Interaction:  Meeting, today 14:30      Summary (editable)
Facts to remember      [x] Competitive pinball fanatic        interest
                       [ ] Prefers Diet Coke                  preference (already recorded)
Tasks                  [x] Contact the program officers he mentioned   due: next week
                       [x] Book next meeting at a pinball bar          due: in 30 days
New people mentioned   [ ] Add "Maj. Lisa Park, program officer" as a contact
Model notes            "Unsure whether 'next week' means a specific date."
[Discard]                                                   [Save to Michael Johnson]
```

Insights: list grouped by severity; each card has title, body, evidence line ("Based on 4 interactions, last on 12 Sep"), and one primary action; dismiss is secondary. Team scope toggle for managers.

Network (`/app/network`), from the network mockup: full-bleed canvas; filter panel (relationship type, industry, minimum score slider, view mode 2D or By company); legend (Strong, Steady, Weak, Drifting rendered as brightness swatches with text labels); node info panel on select (name, title, connections, score, last contact, total deal value, mutual connections, "Open profile"); tools: reset view, find path (pick a target, highlight shortest path), export PNG. No 3D.

Analytics (`/app/analytics`), from the analytics mockup: range selector (Today, Week, Month, Quarter, Year); four stat blocks with deltas; two charts (distribution by band; interactions over time by kind); top relationships table (contact, company, gravity, last interaction, deal value, status) with search; insight cards below. Team tab (manager+): per-member rows (contacts, average gravity, interactions in range, pipeline, overdue) and a workspace-wide distribution.

Onboarding, from the onboarding mockup: five steps with a five-segment progress bar (rectangles, not dots). Step 4 shows integration plates with "Connect" (Google, Microsoft; functional in Phase 3, otherwise a disabled state with "Available soon") and a plain privacy paragraph. Step 5: "Your workspace is ready" with the four things that happen next as a plain list, and one button "Open Gravv".

Settings: profile (name, role, timezone, interests, goals, avatar), workspace (name, slug, defaults), members (list, invite, change role, mark departed), integrations (per-user connections), security (password, MFA enroll/unenroll, sessions), data (export my data, delete account with confirmation and re-authentication).

Landing (`/`): hero headline "Know the gravity of your network" set in the display face, one paragraph, one primary action "Start free", one secondary "See how it works"; a single product screenshot; three short feature statements written as sentences (not a card grid); no testimonials or invented statistics.

### 9.5 Data layer conventions

- Query keys: `['contacts', ws, filters]`, `['contact', ws, id]`, `['timeline', ws, id]`, `['capture', id]`, `['insights', ws, scope]`, `['analytics', ws, range, scope]`, `['network', ws, filters]`.
- Mutations invalidate the narrowest keys; task complete/snooze and insight status use optimistic updates.
- Polling: `['capture', id]` refetches every 2 s while status is not terminal; `['job', id]` likewise for profile regeneration and briefs.
- Errors: Problem Details mapped to toasts (`title` shown; `detail` in a collapsible), field errors to form fields.
- Formatting helpers in `lib/format.ts`: relative time ("3h ago", "2 weeks ago"), currency compact ("$2.5M"), score, dates in the user's timezone.

### 9.6 Voice capture implementation notes

- `navigator.mediaDevices.getUserMedia({ audio: true })`; `MediaRecorder` with the first supported of `audio/webm;codecs=opus`, `audio/mp4`; 32 kbps mono is enough for speech.
- Hard stop at 10 minutes; show elapsed time; level meter via `AnalyserNode` drawn as 32 vertical bars.
- On stop: request upload URL, `PUT` the blob with the returned headers, then call `uploaded`. If offline: keep the blob in IndexedDB (Phase 2 background sync) and show "Will upload when back online".
- Permissions denied: show the text mode with an explanation and a link to browser settings.

### 9.7 Network graph payload and rendering

`GET /network/graph` returns `{ nodes: [{ id, kind: 'me'|'contact', display_name, initials, title, company, industry, relationship_type, gravity_score, band, last_interaction_at, deal_value_cents, connection_count }], edges: [{ id, source, target, strength, kind }] }`. The "me" node is synthetic; edges from "me" to each contact carry `strength = gravity_score`. Rendering: force simulation (`forceManyBody` negative, `forceLink` distance inversely proportional to strength, `forceCenter`), nodes as squares sized 16-36px by score, edge width 1-3px by strength, brightness by band; labels on hover/selection only; devicePixelRatio-aware canvas; quadtree hit testing; pan/zoom; keyboard: arrow keys move selection between nodes; a hidden list of nodes for screen readers.

### 9.8 Accessibility and quality floor

- Visible focus on everything: `outline: 2px solid var(--color-temper-500); outline-offset: 0`.
- Contrast AA verified for all token pairs used for text (documented in `tokens.css` comments).
- Color is never the only signal: bands always have a text label; deltas show sign and number.
- `prefers-reduced-motion`: disables the score blade fill and sheet transitions.
- Touch targets >= 44px on mobile; the dock respects `env(safe-area-inset-bottom)`.
- Lighthouse budget in CI (M7): performance >= 85 on mobile, accessibility >= 95.

---

## 10. Design system: "Forged"

The brief: sleek, modern, sharp edges, strong metal, swords. No random hues, no emojis, nothing that reads as generated. The design language is a machined steel instrument: flat plates with beveled edges, one tempered-gold accent, brightness as the data signal, condensed industrial type for numbers and titles.

### 10.1 Principles

1. Material over decoration. Surfaces are steel plates. Depth comes from a one-pixel light edge on top and a one-pixel dark edge below (a bevel), never from blur or drop shadows.
2. Edges are edges. `border-radius: 0` everywhere. Chamfers (45-degree cuts) appear only on the primary button and the score blade, one corner each.
3. One accent. Tempered straw gold marks the current action, the active destination, focus, and the single hamon divider on Home. It is never a background.
4. Brightness is the signal. Relationship strength maps to how polished the steel is: strong is bright, steady is brushed, weak is dull, drifting is dark oxide. Rust is reserved for risk and destructive actions. There are no other hues.
5. Type carries hierarchy. Big numbers and titles in a condensed industrial display face; everything else in a workhorse sans with tabular figures. No eyebrow labels, no all-caps, no tracked-out text.
6. Motion answers actions. No entrance animations, no ambient particles, no animated counters. One orchestrated moment: the score blade filling when a contact opens.
7. Quiet everywhere except one place per screen. Home has the hamon divider; the contact page has the blade; the network page has the machinist grid. Nothing else competes.

### 10.2 Tokens (`apps/web/src/design/tokens.css`, the only place colors, fonts, spacing, and motion are defined)

```css
@import "tailwindcss";

@theme {
  /* Steel ramp (cool gray with a faint blue cast). Dark theme is the default. */
  --color-steel-950: #0F1214;   /* canvas behind sheets and the network grid */
  --color-steel-900: #161A1E;   /* page background */
  --color-steel-800: #1E2328;   /* plate (card) surface */
  --color-steel-700: #272D34;   /* raised plate, hover, table header */
  --color-steel-600: #343B44;   /* rules and borders */
  --color-steel-500: #4B5560;   /* disabled text, placeholders */
  --color-steel-400: #76818D;   /* secondary text (4.6:1 on steel-800) */
  --color-steel-300: #A3ACB6;   /* body text */
  --color-steel-200: #C9D0D8;   /* primary text */
  --color-steel-100: #E6EAEE;   /* headings */
  --color-steel-050: #F4F6F8;   /* highlight, the blade edge */

  /* Temper: tempered straw-gold, the only accent */
  --color-temper-300: #E2C98A;  /* accent text on dark plates */
  --color-temper-500: #C8A253;  /* primary action fill, focus ring, active nav */
  --color-temper-600: #A8873F;  /* pressed */

  /* Rust: risk and destructive only */
  --color-rust-400: #D4744E;
  --color-rust-500: #B4552F;
  --color-rust-700: #7E3A20;

  /* Oxide: inert / drifting */
  --color-oxide-500: #3F4A55;

  /* Band mapping (brightness encodes strength) */
  --color-band-strong:   var(--color-steel-050);
  --color-band-steady:   var(--color-steel-300);
  --color-band-weak:     var(--color-steel-500);
  --color-band-drifting: var(--color-oxide-500);

  /* Type */
  --font-display: "Big Shoulders", "Big Shoulders Display", "Archivo Narrow", "Arial Narrow", sans-serif;
  --font-sans: "IBM Plex Sans", "Helvetica Neue", Arial, sans-serif;
  --text-xs: 0.75rem;   --text-xs--line-height: 1rem;
  --text-sm: 0.8125rem; --text-sm--line-height: 1.25rem;
  --text-base: 0.9375rem; --text-base--line-height: 1.5rem;
  --text-md: 1rem;      --text-md--line-height: 1.5rem;
  --text-lg: 1.25rem;   --text-lg--line-height: 1.75rem;
  --text-xl: 1.5625rem; --text-xl--line-height: 1.75rem;   /* display */
  --text-2xl: 1.9375rem; --text-2xl--line-height: 2rem;    /* display */
  --text-3xl: 2.4375rem; --text-3xl--line-height: 2.5rem;  /* display, stat numbers */
  --text-4xl: 3.0625rem; --text-4xl--line-height: 3rem;    /* display, landing hero */

  /* Spacing: 8px grid with 4px half-step */
  --spacing: 0.25rem;

  /* Radius: none */
  --radius-none: 0px;

  /* Bevels (the only "shadows") */
  --shadow-plate: inset 0 1px 0 0 rgb(244 246 248 / 0.06), inset 0 -1px 0 0 rgb(15 18 20 / 0.70);
  --shadow-plate-raised: inset 0 1px 0 0 rgb(244 246 248 / 0.10), inset 0 -1px 0 0 rgb(15 18 20 / 0.80);
  --shadow-pressed: inset 0 1px 0 0 rgb(15 18 20 / 0.60), inset 0 -1px 0 0 rgb(244 246 248 / 0.05);

  /* Motion */
  --ease-machined: cubic-bezier(0.2, 0, 0, 1);
  --duration-fast: 120ms;
  --duration-sheet: 200ms;
  --duration-blade: 400ms;
}

/* Non-token utilities used by components (defined once here) */
.edge-highlight { background-image: linear-gradient(90deg, transparent 0%, rgb(244 246 248 / 0.55) 50%, transparent 100%); height: 1px; }
.brushed        { background-image: repeating-linear-gradient(0deg, rgb(244 246 248 / 0.025) 0 1px, transparent 1px 3px); }
.chamfer-br     { clip-path: polygon(0 0, 100% 0, 100% calc(100% - 8px), calc(100% - 8px) 100%, 0 100%); }
.chamfer-tr     { clip-path: polygon(0 0, calc(100% - 8px) 0, 100% 8px, 100% 100%, 0 100%); }
.tnum           { font-variant-numeric: tabular-nums; }
:focus-visible  { outline: 2px solid var(--color-temper-500); outline-offset: 0; }

/* Light theme (optional, M7): same ramp inverted. Apply with data-theme="light" on <html>. */
:root[data-theme="light"] {
  --color-steel-950: #F4F6F8; --color-steel-900: #E9ECEF; --color-steel-800: #DEE2E6; --color-steel-700: #D0D5DB;
  --color-steel-600: #B9C0C8; --color-steel-500: #8E98A3; --color-steel-400: #5E6873; --color-steel-300: #3C444D;
  --color-steel-200: #272D34; --color-steel-100: #1B2025; --color-steel-050: #0F1214;
  --color-temper-500: #9A7A2F; --color-temper-600: #7C6226; --color-temper-300: #6E5620;
}
```

Fonts are self-hosted through `@fontsource` packages (`big-shoulders` variable, or `big-shoulders-display` if that is the package name available; `ibm-plex-sans` 400/500/600) and imported in `src/design/fonts.css`. No Google Fonts requests at runtime.

### 10.3 Typography rules

- Display face for: page titles (`text-2xl`, weight 700), stat numbers (`text-3xl`, weight 800, `tnum`), contact name in the detail header (`text-xl`, weight 700), landing hero (`text-4xl`). Letter-spacing 0 or -0.01em at `text-3xl` and above. Never tracked out, never all-caps.
- Sans face for everything else: body `text-base` weight 400, secondary `text-sm` in steel-400, table cells `text-sm` with `tnum` on numeric columns, buttons `text-sm` weight 500, section headings `text-md` weight 600 in steel-100.
- Line length: content columns max 68ch.
- Sentence case everywhere, including table headers and nav labels.
- Numbers: tabular figures in every table, list, and stat.

### 10.4 Components (props and looks; implement in `components/ui`)

| Component | Look | Rules |
| --- | --- | --- |
| Button | Primary: temper-500 fill, steel-950 text, `chamfer-br`, edge-highlight line on top, pressed uses temper-600 + `shadow-pressed`. Secondary: steel-700 fill, steel-100 text, `shadow-plate`. Ghost: transparent, steel-300 text, hover steel-700. Danger: rust-500 fill, steel-050 text. Height 40px (44px on touch), padding 0 16px. | Label names the action. One primary per view. Loading state swaps the label for "Saving..." text, no spinner icon. |
| IconButton | 40px square, ghost by default | Always has `aria-label`. |
| Field (Input, Textarea, Select) | steel-900 fill, 1px steel-600 border, 2px bottom border steel-500; focus turns the bottom border temper-500 and shows the outline; error turns it rust-500 with the message below in rust-400. Label above in steel-300 `text-sm`. | Placeholder never replaces a label. |
| Plate (card) | steel-800 fill, 1px steel-600 border, `shadow-plate`, padding 16px (24px desktop). Raised variant steel-700 + `shadow-plate-raised`. | No hover transform. Plates are containers, not decoration; do not chop content into plates when a list will do. |
| Tabs | Text tabs in steel-400, active steel-100 with a 2px temper-500 underline whose right end is chamfered (`chamfer-tr` on a 2px bar looks like a blade tip). | Keyboard arrow navigation. |
| Dock / Rail | steel-900 fill with `.brushed` texture, 1px edge-highlight on the top edge (dock) or right edge (rail). Active item: temper-500 icon and label, 2px temper bar on the leading edge. | Four items on mobile, plus the capture button. |
| CaptureButton | 56px square, temper-500 fill, `chamfer-br`, microphone icon in steel-950; recording state: rust-500 fill with a square stop icon. | Docked bottom-right above the dock on mobile; bottom of the rail on desktop. |
| Avatar | Square, initials in the display face weight 700, fill = brushed gradient from steel-600 to band color at 35% opacity over steel-700, 1px steel-500 border. Sizes 32/40/64. | No photos in v1 (avatars table exists for later). |
| ScoreBlade | 6px tall bar, track steel-700, fill = band color, right end `chamfer-tr`; number to the right in `tnum` `text-sm` steel-100 with the band word in steel-400. | Fills from 0 over `--duration-blade` on contact open only; reduced-motion shows the final state. |
| Badge | 1px border, text only, 22px tall, sentence case. Status: text steel-300; band: text in band color; risk: rust-400 border and text. | Never filled. |
| StatBlock | Number `text-3xl` display, label `text-sm` steel-400 below, delta on the same line as the label ("+12 this month" in steel-300, negative in rust-400). | No eyebrow. No animated counting. |
| Table | Header row steel-700 fill, `text-sm` steel-300, rows 44px, hairline steel-600 between rows, hover steel-700 at 50%. Numeric columns right-aligned `tnum`. | Sticky header on desktop; on mobile the same table scrolls horizontally inside `overflow-x: auto`; do not convert to cards. |
| Timeline | 2px steel-600 vertical rail, 8px square markers (band color for score changes, steel-300 for interactions), kind icon, `text-sm` timestamp in steel-400. | Group by day with a plain date heading. |
| Sheet (mobile) / Panel (desktop) | steel-800 plate sliding from the bottom (mobile) or the right (desktop), 1px temper-500 top/left edge, `--duration-sheet` slide. | Focus trapped; escape closes. |
| Dialog | Centered plate, max 480px, 1px steel-500 border. | Confirmation dialogs state the consequence in one sentence. |
| Toast | Bottom-left plate, steel-700, `text-sm`; error variant with rust-500 left edge 2px. | Auto-dismiss 5 s, never stacks more than 3. |
| EmptyState | Title in steel-100, one sentence, one primary action. | No illustrations. |
| Skeleton | steel-700 rectangles matching the content shape. | No shimmer animation. |
| Chip (filter) | 1px steel-600 border, steel-300 text; selected: steel-100 text, temper-500 border. | |
| Slider | 2px track steel-600, filled portion steel-200, 12px square thumb steel-050. | |
| Progress (onboarding) | Five 2px-tall rectangles; completed steel-050, current temper-500, upcoming steel-600. | Rectangles, not dots. |

### 10.5 Charts and canvas

- Recharts: `isAnimationActive={false}`; grid lines steel-700 1px; axes text steel-400 `text-xs`; bars flat band colors with 1px steel-900 gap; lines 1.5px steel-100 with 4px square markers; tooltip rendered as a Plate.
- Network canvas: background steel-950 with a 32px grid in steel-800 (drawn once per frame, offset by the pan); nodes square; the "me" node 44px with a 1px temper-500 outline; selected node outline temper-500 2px; edges 1-3px in band brightness at 60% opacity; labels `IBM Plex Sans 12px` in steel-200 on hover or selection.
- Level meter (voice): 32 vertical bars, 3px wide, steel-300; recording state rust-400.

### 10.6 Copy rules

- Sentence case for everything. No exclamation marks. No emojis.
- Buttons name the action and keep the same verb through the flow ("Save note" -> toast "Note saved").
- Meta text uses commas or two lines, never middle dots: "Space Force, Program Director".
- Errors say what happened and what to do next: "Recording could not be uploaded. Check your connection and try again."
- Empty states invite an action, not a mood.
- Relative times: "3h ago", "2 weeks ago", "overdue 9 days".
- Labels are plain nouns; the metaphor appears only as "Gravity" (score) and "orbit" (cadence) per Section 1.4.

### 10.7 Forbidden list (lint where possible; grep in CI for the rest)

`border-radius` other than 0; `box-shadow` other than the three bevel tokens; `backdrop-filter`; CSS gradients other than `.edge-highlight`, `.brushed`, and the avatar fill; any hex color outside `tokens.css`; purple, blue, cyan, green, or yellow anywhere (including chart series); `text-transform: uppercase`; `letter-spacing` greater than 0; monospace fonts (except code blocks in docs); Unicode arrows in labels; emoji in any file; entrance animations (`fade-in`, `slide-up` on mount); animated number counters; particle or "neural" canvas backgrounds; per-card hover `transform`; numbered decoration markers; system font stacks as the primary face; illustrations or stock imagery.

---
## 11. AI features specification

### 11.1 Principles

- Rules detect, models narrate. Scores, bands, due dates, and insight triggers are deterministic (Section 7.9, 7.10). The LLM extracts structure from free text and writes summaries; it does not decide what is true about a relationship.
- Structured outputs only. Every model call returns a Pydantic-validated object. Free-text prompts are limited to summaries and briefs, which are stored as text and never executed.
- Human in the loop. Extractions are proposals; the user confirms. Exceptions in 11.5.
- Untrusted input. Transcripts and notes are wrapped in explicit delimiters and the prompt states that instructions inside them must be ignored. Prompt injection tests exist in `tests/unit/ai/test_injection.py` using the fake provider's fixture set and, when enabled, a live provider marker.
- Provenance. Every AI artifact stores `model`, `prompt_version`, and inputs hash in metadata so results can be reproduced and audited.

### 11.2 Extraction (`capture.extract`)

Prompt inputs: current datetime and user timezone; the user's name and role; the selected contact (if any) with active facts; candidate contacts from name matching (id, name, company, title); the text within `<capture>...</capture>`.

Instructions (summarized; full template in `app/ai/prompts/extract/v1.md`):

- Identify which one contact this capture is primarily about; if none of the candidates match, return `contact_match: null` and list the person under `mentioned_people`.
- Produce one interaction: infer `kind` (meeting, call, email, message, note), `occurred_at` when stated ("this morning", "yesterday at 3") relative to the current datetime, `subject`, a one-sentence `summary`, and `body` (a clean, lightly edited version of the transcript, first person preserved).
- Facts: durable things worth remembering about the contact (preferences, dislikes, interests, family, ambitions, communication style). Exclude anything already in the provided active facts unless it contradicts; contradictions go in `facts` with `supersedes: true` and a note in `needs_review`.
- Tasks: explicit and clearly implied follow-ups. Resolve relative dates; when a date is vague, leave `due_at` null and explain in `needs_review`.
- Mentioned people and companies; edges when the text states who knows whom.
- Sentiment: overall tone of the interaction from the practitioner's perspective, label plus score -1..1.
- Output must validate against `CaptureExtraction`. No prose outside the structure.

### 11.3 Profile synthesis (`profile.synthesize`)

Inputs: contact basics; all active facts; last 30 interactions (summaries, dates, sentiment); open tasks; open opportunities; the user's interests (for common ground). Output `ContactProfileDraft { summary (<= 120 words), communication_style (<= 12 words), remember (3-8 short items), risks (0-4), talking_points (2-5), common_ground (0-3) }`. Written in plain sentences, no bullet symbols in strings, no exclamation marks. Marks the profile `stale = false`.

### 11.4 Pre-meeting brief (`brief.generate`)

Inputs: the profile, timeline of the last 90 days, open due-outs, related opportunities, mutual connections, recent context items (Phase 3). Output: a text brief of at most 300 words in sections "Where things stand", "Open items", "What to bring up", "Watch for", followed by `BriefStructured { due_outs: [...], suggested_questions: [...] }`. Stored as an `insights` row of kind `briefing` (body = text, evidence = structured) and returned by the job. Offered on the contact page as "Prepare a brief" and read aloud on mobile via the Web Speech API (`speechSynthesis`) as a Phase 2 nicety.

### 11.5 Auto-apply exceptions

When `workspaces.settings.auto_apply_low_risk_facts = true`: facts of category `preference`, `interest`, or `dislike` with confidence >= 0.9 are applied at extraction time with `source = ai` and shown with an "Added automatically" badge that has a one-tap undo. Tasks, edges, contact creation, and contradictions are never auto-applied.

### 11.6 Evaluation

`tests/ai/cases/*.yaml` holds 30+ captures (sales, government, diplomacy phrasing; ambiguous dates; injection attempts; multiple people; no match). Each case has expected facts/tasks (fuzzy match on normalized text). `make ai-eval` runs them against the configured provider and prints precision/recall per field; the fake provider must pass 100% (fixtures are the expected outputs); live providers must exceed 0.85 precision on facts and tasks before a prompt version ships.

---

## 12. Testing strategy

### 12.1 Backend

- Unit: scoring engine (table-driven, 40+ cases including boundaries), insight rules, cursor encoding, crypto, JWT verification (JWKS and HS256 with generated keys), prompt rendering, extraction schema validation.
- Integration (against the local Supabase Postgres started by the CLI): every endpoint has at least one happy-path and one authorization test using `httpx.AsyncClient` with tokens minted by a test helper (`mint_token(user_id, aal)` signed with the local JWT secret or a test JWKS). Each test runs inside a transaction that is rolled back; fixtures create users through the Supabase admin API once per session and reuse them.
- RLS tests (`tests/rls`): pure SQL through two RLS-bound sessions (user A in org X, user B in org Y, user C viewer in X) asserting: no cross-workspace reads, private contacts invisible to teammates, viewer cannot insert, departed member loses access instantly, `credentials_enc` unreadable, `jobs` unreadable.
- Worker: handlers run inline with the fake AI and fake transcription; idempotency test re-runs each handler and asserts no duplicates.
- Schema parity test (Section 5.8).
- Contract test: `openapi.json` snapshot; changes require regenerating the TS client in the same commit.

### 12.2 Frontend

- Vitest + Testing Library for `components/ui` (each component: renders, keyboard, focus ring present, forbidden styles absent), formatting helpers, query hooks with MSW mocks generated from the OpenAPI schema.
- Design lint: a CI script greps `apps/web/src` for the forbidden list (Section 10.7) and fails on hits.
- Playwright (`apps/web/e2e`) against `make dev` with seeded data and fake AI: sign in; onboarding completes; create a contact; text capture "Met the Colonel, he loves competitive pinball, remind me to call the program officers next Tuesday" -> proposal shows one fact and one task -> confirm -> contact page shows the fact and task and an updated score; network page renders and selecting a node opens the panel; analytics summary shows seeded numbers; invite flow via the local mail inbox; departed member cannot open the workspace.
- Visual regression (optional from M7): Playwright screenshots of Home, Contact detail, Analytics at 390px and 1280px compared against committed baselines.

### 12.3 CI (`.github/workflows/ci.yml`)

Jobs: `api` (uv sync, ruff, mypy, supabase start, db reset, pytest with coverage >= 80% on `app/domain` and `app/scoring`), `web` (pnpm install, eslint, prettier, tsc, vitest, design lint, build), `contract` (`make gen` and `git diff --exit-code`), `db` (`supabase db reset` from scratch and `make db-diff` empty), `e2e` (nightly and on `e2e` label), `docker` (build both images). All required to merge.

---

## 13. Deployment (AWS) and environments

### 13.1 Environments

| Env | Supabase project | API/worker | Web | Purpose |
| --- | --- | --- | --- | --- |
| local | Supabase CLI (Docker) | uvicorn + worker processes | Vite dev server | development and tests |
| staging | `gravv-staging` (region us-east-1) | App Runner `gravv-api-staging`, `gravv-worker-staging` | S3 + CloudFront `staging.gravv.app` | every merge to `main` |
| prod | `gravv-prod` (us-east-1, Pro plan, PITR) | App Runner `gravv-api`, `gravv-worker` | S3 + CloudFront `app.gravv.app`; landing at `gravv.app` | release tags `v*` |

Supabase's hosted infrastructure runs on AWS; choosing the same region keeps API-to-database latency in the low single-digit milliseconds. Domains and certificates via Route 53 and ACM.

### 13.2 Architecture (Stage 1: minimum overhead)

```
Route 53
  gravv.app, app.gravv.app  -> CloudFront (OAC) -> S3 bucket (SPA + landing), response headers policy (CSP, HSTS)
  api.gravv.app             -> App Runner service gravv-api (custom domain, TLS managed)
                               - image from ECR, 1 vCPU / 2 GB, min 1 / max 10 instances, concurrency 80
                               - health check GET /readyz
                               - env from SSM SecureString (DATABASE_URL via Supavisor 6543, keys, LLM keys)
                            App Runner service gravv-worker
                               - same image, command `python -m app.worker`
                               - exposes GET /healthz on port 8080 (tiny aiohttp/uvicorn thread) for the health check
                               - min 1 / max 1 instance in Stage 1 (raise when job latency grows)
                               - DATABASE_URL_WORKER via direct connection (5432, session mode) for LISTEN/NOTIFY
  Supabase hosted: Postgres, Auth, Storage (S3-backed), daily backups + PITR
  CloudWatch: App Runner logs and metrics; alarms (13.7)
  SSM Parameter Store: secrets; KMS default key
  ECR: gravv-api repository, image tags = git sha
  IAM: GitHub OIDC role scoped to ECR push, App Runner deploy, S3 sync, CloudFront invalidation
```

Why App Runner first: no VPC, load balancer, or cluster to manage; HTTPS, autoscaling, and rolling deploys are built in; cost at idle is roughly two small instances. It supports everything in this plan because the database is outside the VPC (Supabase) and the worker needs no inbound traffic.

### 13.3 Stage 2 (when needed): ECS Fargate in a VPC

Trigger conditions: private networking to a self-hosted Supabase or RDS, VPC-only integrations, more than ~10 API instances, or the need for a scheduled task runner with different sizing than the API. Terraform modules for `vpc`, `alb`, `ecs-cluster`, `ecs-service` (api and worker) are added under `infra/terraform/modules` at that time; the container image and configuration do not change.

### 13.4 Terraform layout

```
infra/terraform/
  modules/
    ecr/            # repository + lifecycle policy (keep last 30)
    apprunner/      # service, autoscaling config, custom domain, IAM instance role (SSM read)
    static-site/    # S3 (private) + CloudFront + OAC + ACM + response headers policy + Route 53 records
    secrets/        # SSM parameters (values supplied out of band with `aws ssm put-parameter`; TF stores names only)
    github-oidc/    # OIDC provider + deploy role with least privilege
    alarms/         # CloudWatch alarms + SNS topic (email)
  envs/
    staging/main.tf  terraform.tfvars  backend.tf (S3 state bucket gravv-tfstate, key envs/staging, native locking)
    prod/main.tf     terraform.tfvars  backend.tf
```

`make infra-plan env=staging` and `make infra-apply env=staging` wrap `terraform -chdir=infra/terraform/envs/staging`. The Supabase project itself is created in the Supabase dashboard (or with the Supabase Terraform provider if preferred); its URL and keys are then stored in SSM.

### 13.5 Container images

`apps/api/Dockerfile`: multi-stage, `python:3.12-slim`, `uv sync --frozen --no-dev`, non-root user, `EXPOSE 8080`, default `CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "2"]`; worker overrides the command. `ffmpeg` installed only if a transcription provider needs format conversion (Deepgram and OpenAI accept webm/opus directly, so omit by default).

`apps/web` builds to static files; no runtime container in AWS. `docker-compose.yml` exists only for local parity checks (`make build && docker compose up`).

### 13.6 CI/CD pipelines

- `deploy-staging.yml` (on push to `main`, after `ci.yml` succeeds): assume the OIDC role; `supabase db push --db-url $STAGING_DB_URL`; build and push the API image tagged with the sha; update both App Runner services to the new tag and wait for `RUNNING`; build the web app with staging env; `aws s3 sync` with immutable caching for hashed assets and `no-cache` for `index.html`; CloudFront invalidation `/index.html` `/`; run Playwright smoke against staging.
- `deploy-prod.yml` (on tag `v*`): same steps against prod with a manual approval environment gate in GitHub; migrations first, then services, then the SPA.
- Rollback: re-run the prod workflow with a previous tag (images are immutable); migrations are forward-only and written to be backward compatible (Section 5.8).

### 13.7 Observability and operations

- Logs: structlog JSON to stdout; App Runner ships to CloudWatch Logs; retention 30 days staging, 90 days prod.
- Request id in every log line and every Problem response.
- Metrics: App Runner built-ins (requests, 2xx/4xx/5xx, latency, instance count); custom metrics emitted as structured log lines and turned into CloudWatch metric filters: `jobs_dead_total`, `jobs_queue_depth` (worker logs every minute), `llm_tokens_total`, `capture_latency_seconds`.
- Alarms (SNS email): 5xx rate > 2% for 5 min; p95 latency > 1.5 s for 10 min; any dead job; queue depth > 200 for 15 min; worker health check failing; Supabase database CPU > 80% (via Supabase alerts).
- Sentry optional for both API and web (`SENTRY_DSN`), with PII scrubbing enabled.
- Runbook (`docs/RUNBOOK.md`): rotating keys, re-queuing dead jobs (`make jobs-requeue id=...`), restoring a backup, revoking a compromised integration, scaling App Runner limits.

### 13.8 Cost envelope (indicative, early stage)

Supabase Pro ~$25/mo (+ PITR add-on for prod), App Runner two services at minimum size ~$30-60/mo, S3 + CloudFront < $5/mo, Route 53 ~$1/mo, LLM and transcription usage-based. Staging can pause the worker service overnight.

---

## 14. Scaling plan

| Pressure | First response (no new infrastructure) | Later |
| --- | --- | --- |
| API CPU or latency | Raise App Runner max instances and concurrency; enable HTTP caching headers for analytics endpoints (60 s); add `contact_overview` materialized view refreshed by the worker every 5 min for large workspaces | ECS Fargate (Stage 2), read replicas via Supabase |
| Database connections | Supavisor transaction pooling already in place; keep transactions short; batch nightly scoring per workspace | Larger Supabase compute; connection limits per service |
| Job throughput | Raise worker max instances (claim query is safe with N workers); per-kind priorities; batch profile synthesis | SQS + Lambda for transcription fan-out if audio volume dominates |
| Search | pg_trgm and tsvector indexes; pgvector HNSW index on `interactions.embedding` for semantic search ("what did he say about program officers") | Dedicated search service only if needed |
| Analytics for large orgs | Pre-aggregated daily rollups in `workspace_daily_metrics` written by the scoring job | Warehouse export (Parquet to S3) for BI |
| Rate limiting across instances | In-memory limiter per instance is acceptable until instance count > 3 | Shared limiter in Postgres (`unlogged` table) or CloudFront/WAF rate rules in front of the API |
| Storage | Supabase Storage with lifecycle purge | S3 lifecycle to Glacier for retained audio |
| Multi-region / data residency | Not planned | Separate Supabase projects per region with workspace routing |
| Native mobile | PWA with background sync | Capacitor wrapper reusing the web app; push notifications via APNs/FCM for due-outs |
| Integrations (Gmail, Outlook, Calendar, CRM) | Phase 3 sync jobs on the worker with per-provider cursors and idempotent upserts by `external_id` | Webhook receivers (Gmail push, Graph subscriptions) on the API |

---

## 15. Milestones and acceptance criteria

Each milestone: implement, write tests, run `make check`, update `docs/PROGRESS.md`, commit with a conventional message (`feat(contacts): ...`). Do not skip ahead.

### M0 - Foundation (scaffold and local stack)

Deliverables: repo layout (Section 3); `Makefile`; `.env.example`; Supabase CLI config; migrations `0001`-`0009` (extensions, identity, core, ops, functions, views, storage, RLS, roles); seed data; FastAPI skeleton with `/healthz`, `/readyz`, Problem Details, logging, JWT verification, RLS-bound sessions; worker skeleton with the claim loop and a `noop` job; web skeleton with tokens, fonts, `AppShell`, auth screens, generated API client; CI with all jobs.

Accept when: `make setup && make dev` gives a sign-in page at 5173 and `/readyz` returns 200; `make check` passes; RLS tests prove workspace isolation on `contacts`; `make db-reset` succeeds from zero.

### M1 - Identity, workspaces, onboarding

Deliverables: `/me`, `/me/onboarding`, `/workspaces`, members, invitations (email through local inbox), departure, role guards; onboarding wizard; settings profile/workspace/members/security (password, MFA enroll).

Accept when: a new user signs up, lands in onboarding, finishes five steps, sees Home; owner invites a second user who accepts from the inbox link and appears in Members; departed member gets 403 on workspace routes; RLS tests for memberships and profiles pass.

### M2 - Contacts, companies, facts, interactions, timeline

Deliverables: contacts CRUD with search/filters/sort and cursor pagination; companies; facts with supersede; manual interactions; timeline; contact detail page with all tabs; share to organization and copy to personal; audit entries; design system components used throughout (Button, Field, Plate, Tabs, Table, Timeline, Avatar, ScoreBlade, Badge, StatBlock, Sheet, Dialog, Toast, EmptyState, Skeleton, Chip).

Accept when: Playwright creates a contact, adds a fact and a meeting note, sees them on the timeline; a private contact is invisible to a teammate; design lint passes; Lighthouse accessibility >= 95 on Contact detail.

### M3 - Capture pipeline (text and voice) with AI extraction

Deliverables: captures endpoints, signed uploads, transcription and extraction jobs, provider interfaces with Anthropic + fake implementations, prompt v1, proposal review screen, confirm/discard, idempotency, token budget, injection tests.

Accept when: the e2e capture scenario in 12.2 passes with the fake provider; with `LLM_PROVIDER=anthropic` and a key, the same scenario produces a fact and a task from a real transcript; a repeated confirm does not duplicate facts.

### M4 - Scoring, insights, Home, Analytics

Deliverables: scoring engine and nightly job; immediate rescoring after captures; `relationship_scores` history; insight rules and job; insights endpoints and screen; Home dashboard; Analytics (me scope) with charts and top relationships table; scheduler with leader lock.

Accept when: seeded data yields the expected bands (Sarah Martinez drifting, Emily Rodriguez strong); insight `at_risk` appears for Sarah Martinez and "Create task" creates a task; analytics summary matches SQL-computed numbers in a test; charts contain no forbidden colors.

### M5 - Network graph, tasks, opportunities

Deliverables: contact edges, `/network/graph` and `/network/paths`, network page with canvas, filters, node panel, path finder, PNG export; tasks screen with complete/snooze; opportunities screen and contact roles; pipeline value flows into Home and Analytics.

Accept when: the seeded graph renders with the me-node and 10 contacts; selecting Col. Michael Johnson shows mutual connections Dr. James Chen and Gen. Patricia Williams; path finder from me to NASA highlights a path through Dr. James Chen; keyboard navigation works; tasks and opportunities e2e pass.

### M6 - Organization features and data portability

Deliverables: team analytics tab; manager visibility rules; workspace settings (default visibility, cadence, auto-apply facts, MFA requirement); exports (personal, my contributions, workspace) as zipped JSON + CSV via signed URL; account deletion; departure export automation; retention purge job.

Accept when: manager sees per-member metrics and members do not; export downloads and contains the user's contacts and interactions; deleting a test account removes personal data and tombstones organization records.

### M7 - Hardening and first AWS deployment

Deliverables: rate limiting, security headers and CSP, dependency audits, audit log coverage, PWA manifest and service worker, light theme (optional), landing page, Terraform for staging and prod, GitHub OIDC, deploy workflows, alarms, runbook, Lighthouse budgets, visual regression baselines.

Accept when: staging is reachable at its domains with a real sign-in through hosted Supabase; the Playwright smoke passes against staging; an intentionally dead job triggers the alarm email; `terraform plan` for prod is clean.

### M8 - Phase 2 and 3 backlog (after v1 ships)

Semantic search with embeddings; briefing read-aloud; background sync for offline captures; Google and Microsoft OAuth integrations (Gmail, Outlook, Calendar) with sync jobs and calendar-driven briefings; CRM sync (Salesforce, HubSpot) for interactions and opportunities; context feed (news) with relevance scoring; Slack notifications; partner API with `api_keys`; Capacitor mobile wrapper with push notifications; hiring-evaluation views (network breadth) from the concept document.

---

## Appendix A - Makefile skeleton

```make
.DEFAULT_GOAL := help
SHELL := /bin/bash

help: ; @grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "%-14s %s\n", $$1, $$2}'

setup: ## first-time setup
	cd apps/api && uv sync
	cd apps/web && pnpm install
	pre-commit install
	supabase start
	$(MAKE) db-reset
	$(MAKE) gen

dev: ## run everything locally
	supabase start >/dev/null 2>&1 || true
	process-compose up   # or: run the three commands below in three terminals
	# cd apps/api && uv run uvicorn app.main:app --reload --port 8000
	# cd apps/api && uv run python -m app.worker
	# cd apps/web && pnpm dev

db-reset: ## rebuild the local database from migrations and seed
	supabase db reset
	infra/scripts/setup_roles.sh local
	cd apps/api && uv run python scripts/seed_users.py

db-migrate: ## make db-migrate name=<change>
	supabase migration new $(name)

db-diff: ## fail if the live schema drifted from migrations
	supabase db diff --linked=false | tee /tmp/diff.sql; test ! -s /tmp/diff.sql

gen: ## regenerate the TypeScript API client
	cd apps/api && APP_ENV=test uv run python scripts/export_openapi.py > ../web/src/lib/api/openapi.json
	cd apps/web && pnpm exec openapi-typescript src/lib/api/openapi.json -o src/lib/api/schema.d.ts

lint: ## all linters
	cd apps/api && uv run ruff check . && uv run ruff format --check . && uv run mypy .
	cd apps/web && pnpm lint && pnpm prettier --check . && pnpm tsc --noEmit && pnpm design-lint

test: ## unit + integration tests
	cd apps/api && uv run pytest -q
	cd apps/web && pnpm test -- --run

test-e2e: ## playwright against the local stack
	cd apps/web && pnpm exec playwright test

check: lint test db-diff ## the milestone gate

build: ## container image and static bundle
	docker build -t gravv-api:local apps/api
	cd apps/web && pnpm build
```

## Appendix B - `.env.example` additions for hosted environments

```dotenv
# staging / prod (values live in SSM, listed here for reference)
SUPABASE_URL=https://<project-ref>.supabase.co
DATABASE_URL=postgresql+asyncpg://gravv_api:<pw>@aws-0-us-east-1.pooler.supabase.com:6543/postgres
DATABASE_URL_WORKER=postgresql+asyncpg://gravv_worker:<pw>@db.<project-ref>.supabase.co:5432/postgres
CORS_ORIGINS=https://app.gravv.app
LLM_PROVIDER=anthropic
TRANSCRIPTION_PROVIDER=openai
VITE_API_URL=https://api.gravv.app
```

## Appendix C - `CLAUDE.md` for the repository

```markdown
# Gravv - working agreements

Read docs/GRAVV_BUILD_PLAN.md before starting any task. Follow the milestone order in Section 15.

## Commands
- make dev / make check / make test / make test-e2e / make gen / make db-reset / make db-migrate name=<x>

## Rules
- No emojis anywhere (code, comments, commits, UI, seed data, docs).
- Colors, fonts, radii, shadows, and motion come only from apps/web/src/design/tokens.css. No arbitrary Tailwind values.
- border-radius is 0. Depth is bevels (shadow-plate tokens). No blur, no drop shadows, no gradients except .edge-highlight, .brushed, and avatar fills.
- Every table in public has RLS. The API binds the caller's identity per transaction; never use the postgres role or the secret key for user data.
- Migrations are SQL files under supabase/migrations; never edit an applied migration; keep them backward compatible.
- Routers hold no SQL; services hold no FastAPI; repositories hold SQL.
- Every endpoint gets an integration test and an authorization test. Every scoring or rule change gets unit cases.
- AI output is a proposal. Structured outputs only. Notes and transcripts are untrusted text.
- Set operation_id on every route; run make gen after API changes and commit the generated client.
- Copy: sentence case, no exclamation marks, buttons name the action.
- Conventional commits. Update docs/PROGRESS.md at the end of each milestone and docs/DECISIONS.md on any deviation from the plan.
- Prefer the latest stable versions of dependencies; pin them in lockfiles.
```

## Appendix D - Open questions and assumptions (resolve with the product owner; defaults chosen here)

1. Brand vocabulary: the plan limits the gravity metaphor to "Gravity" and "orbit" (Section 1.4). Default: keep it limited; all labels live in `copy.ts`.
2. Score weights and cadence defaults (Section 7.9) are initial values; expose them per workspace in settings after M4 if practitioners disagree with the ranking.
3. Session storage in the browser: supabase-js default (localStorage) for v1. If security review requires it, move to a cookie-based BFF in the API.
4. Transcription provider: OpenAI Whisper API by default in hosted environments; Deepgram if lower latency matters; either is a config change.
5. Email delivery in hosted environments: Supabase's built-in SMTP is rate-limited; configure a custom SMTP (Amazon SES) before inviting real users.
6. Billing and plans are out of scope for v1; `workspaces.plan` and `memberships.grace_until` exist to support them later.
7. LinkedIn has no practical API for this use case; the onboarding card stays as "Available soon" indefinitely unless a compliant data path is found.
8. Landing page copy (Section 9.4) intentionally omits the mockup's invented statistics.

## Appendix E - Glossary

Capture: one tap-to-talk recording or quick note that becomes an interaction after review. Fact: a durable thing to remember about a contact. Gravity: relationship health score 0-100. Band: strong / steady / weak / drifting. Orbit / cadence: expected days between interactions. Due-out: an open task or a cadence that has come due. Plate: the design system's card surface. Blade: the score bar. Workspace: a personal or organization tenant. Membership: a user's role inside a workspace. Proposal: AI-extracted structure awaiting confirmation.
