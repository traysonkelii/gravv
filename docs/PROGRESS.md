# Progress

| Milestone | Status | Notes |
| --- | --- | --- |
| M0 Foundation | done | Local stack, 9 migrations, seed, API + worker skeleton, web shell + auth, CI |
| M1 Identity, workspaces, onboarding | done | /me, workspaces, members, invitations via Mailpit, departure, ownership transfer with MFA, onboarding wizard, settings |
| M2 Contacts, companies, facts, interactions | done | Contacts CRUD with search, filters, sort, cursor pagination; companies; facts with supersede; interactions; timeline; share and copy; detail page |
| M3 Capture pipeline | done | Text and voice captures, signed uploads, transcription and extraction jobs, profile synthesis, proposal review, token budget, injection tests, AI eval |
| M4 Scoring, insights, Home, Analytics | done | Score engine, nightly and immediate rescoring, insight rules, scheduler with advisory lock, Home dashboard, Insights, Analytics with charts |
| M5 Network, tasks, opportunities | done | Contact edges, network graph and path finder on canvas, tasks with complete and snooze, opportunities with contact roles |
| M6 Organization features, data portability | done | Exports (personal, my contributions, workspace) as zipped JSON and CSV via signed URLs, departure export email, account deletion with tombstones, retention purge |
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

## M3 acceptance
- Playwright: from a contact page, the text capture "Met the Colonel, he loves competitive ..., remind me to call
  the program officers next Tuesday" produces a proposal with one fact and one task; confirming shows both on the
  contact and the interaction on the timeline.
- API: text and voice round trips run the jobs inline with the fake provider; a repeated confirm does not duplicate
  facts or tasks; upload-url validation; missing upload returns 409; budget exhaustion fails the capture softly;
  extract=true on a manual note produces a review capture that updates the same note.
- `make ai-eval` runs 30 cases against the configured provider; the fake provider passes 100 percent.
- Live provider check (LLM_PROVIDER=anthropic) is a configuration change; not run in this environment (no key).

## M4 acceptance
- Seeded data yields Sarah Martinez drifting and Emily Rodriguez strong (API test against the seed).
- The at_risk insight appears for Sarah Martinez; acting on it creates a task (API test and Playwright).
- Analytics summary matches SQL-computed contact count, average gravity, and pipeline (API test).
- Charts render only token colors (design lint plus a Playwright check of every rect fill).
- Score engine: 50 unit cases including the drifting boundary, half-life recency, frequency cap, reciprocity,
  depth, momentum, status rules, and next_due.

## M5 acceptance
- Playwright: the seeded graph renders with the me-node and the ten seeded contacts; selecting Col. Michael Johnson
  shows mutual connections Dr. James Chen and Gen. Patricia Williams; the path finder from me to NASA resolves
  through Dr. James Chen; arrow keys move the selection.
- Playwright: a task is added, snoozed, and completed; a deal is created, linked to a contact with a role, and
  shows on the contact's Deals tab.
- API: canonical edge ordering with reverse-order upsert, graph filters (industry, minimum score), shortest paths,
  task lifecycle with immediate rescoring, opportunity lifecycle with pipeline totals flowing into analytics.

## M6 acceptance
- Managers see per-member metrics and members do not (API tests on /analytics/team and scope=team; Playwright
  checks the Team tab is absent for a member and present for a manager).
- Exports download through a signed URL and contain the user's contacts and interactions (API test inspects the
  zip; Playwright downloads a personal export from Settings, Data).
- Deleting a test account removes personal data, departs organization memberships, tombstones the profile, and
  organization records keep their author (API test). Deletion needs a token from the last five minutes and aal2
  when MFA is enrolled.
- Departure enqueues a my_contributions export and emails the link (API test through Mailpit).
- Retention purge removes soft-deleted rows older than 30 days, audio after 30 days unless retain_audio, and
  expired export files.
