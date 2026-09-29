# Progress

| Milestone | Status | Notes |
| --- | --- | --- |
| M0 Foundation | done | Local stack, 9 migrations, seed, API + worker skeleton, web shell + auth, CI |
| M1 Identity, workspaces, onboarding | not started | |
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
