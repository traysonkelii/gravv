-- Operational tables: job queue, audit log, exports.
create table jobs (
  id            uuid primary key default gen_random_uuid(),
  kind          text not null,
  payload       jsonb not null default '{}'::jsonb,
  workspace_id  uuid references workspaces(id) on delete cascade,
  user_id       uuid references profiles(id) on delete set null,
  status        job_status not null default 'queued',
  run_after     timestamptz not null default now(),
  priority      smallint not null default 5,
  attempts      smallint not null default 0,
  max_attempts  smallint not null default 5,
  locked_by     text,
  locked_at     timestamptz,
  last_error    text,
  result        jsonb,
  dedupe_key    text,
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
  action         text not null,
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
