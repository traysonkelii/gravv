# Progress

| Milestone | Status | Notes |
| --- | --- | --- |
| M0 Foundation | done | Local stack, 9 migrations, seed, API + worker skeleton, web shell + auth, CI |
| M1 Identity, workspaces, onboarding | done | /me, workspaces, members, invitations via Mailpit, departure, ownership transfer with MFA, onboarding wizard, settings |
| M2 Contacts, companies, facts, interactions | not started | |
| M3 Capture pipeline | not started | |
| M4 Scoring, insights, Home, Analytics | not started | |
| M5 Network, tasks, opportunities | not started | |
| M6 Organization features, data portability | not started | |
| M7 Hardening and AWS | not started | |

## M0 acceptance
- `make setup && make dev`: sign-in page at http://127.0.0.1:5173, `/readyz` returns 200.
- `make check` passes (ruff, mypy, eslint, prettier, tsc, design lint, pytest, vitest, db-diff).
- RLS tests prove workspace isolation on contacts, private-contact invisibility, viewer read-only,
  instant loss of access on departure, and that jobs and credentials are unreadable.
- `make db-reset` succeeds from zero.

## M1 acceptance
- Playwright: a new user signs up, lands in onboarding, finishes five steps, sees Home.
- Playwright: the owner invites a second user who accepts from the local inbox link and appears in Members;
  after being marked departed the member gets 403 on workspace routes and keeps the personal workspace.
- RLS tests: profiles are own-row only; member_directory and memberships are scoped to shared workspaces;
  only admins insert memberships; members cannot promote themselves.
- Settings: profile, workspace (admin-gated), members, integrations (available soon), security (password, TOTP).
