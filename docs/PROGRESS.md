# Progress

| Milestone | Status | Notes |
| --- | --- | --- |
| M0 Foundation | done | Local stack, 9 migrations, seed, API + worker skeleton, web shell + auth, CI |
| M1 Identity, workspaces, onboarding | done | /me, workspaces, members, invitations via Mailpit, departure, ownership transfer with MFA, onboarding wizard, settings |
| M2 Contacts, companies, facts, interactions | done | Contacts CRUD with search, filters, sort, cursor pagination; companies; facts with supersede; interactions; timeline; share and copy; detail page |
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

## M2 acceptance
- Playwright: create a contact, add a note to remember and a meeting note, both appear (facts tab, timeline,
  overview last interaction).
- Playwright: a private contact is invisible to a teammate in the list and by direct URL.
- Playwright + axe-core: the contact detail page has no serious or critical WCAG 2.0 A/AA violations
  (stands in for the Lighthouse accessibility budget until M7 wires Lighthouse into CI).
- Design lint passes; all UI components from Section 10.4 used by M2 exist under components/ui.
- API: 53 tests including private visibility, role rules on edits, supersede, timeline merge, share and copy.
