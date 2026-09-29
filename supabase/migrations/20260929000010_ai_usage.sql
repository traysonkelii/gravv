-- Provider token usage per workspace, for the daily budget check (Section 7.7). Worker-only.
create table ai_usage (
  id             bigint generated always as identity primary key,
  workspace_id   uuid not null references workspaces(id) on delete cascade,
  user_id        uuid references profiles(id) on delete set null,
  kind           text not null,                          -- capture.extract, profile.synthesize, brief.generate, insights.narrate
  model          text not null,
  input_tokens   int not null default 0,
  output_tokens  int not null default 0,
  created_at     timestamptz not null default now()
);
create index idx_ai_usage_workspace_day on ai_usage (workspace_id, created_at desc);
alter table ai_usage enable row level security;
-- no policies for authenticated: deny all; the worker (service_role) reads and writes.
