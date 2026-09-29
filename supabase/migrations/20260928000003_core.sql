-- Relationship data: companies, contacts, facts, profiles, interactions, captures, tasks,
-- opportunities, edges, scores, insights, context items, integrations.
create table companies (
  id            uuid primary key default gen_random_uuid(),
  workspace_id  uuid not null references workspaces(id) on delete cascade,
  name          text not null,
  domain        citext,
  industry      text,
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
  honorific            text,
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
  next_due_at          timestamptz,
  origin_contact_id    uuid references contacts(id) on delete set null,
  source               text not null default 'manual',
  search_vector        tsvector generated always as (
                         to_tsvector('simple', coalesce(first_name,'') || ' ' || coalesce(last_name,'') || ' ' || coalesce(title,'') || ' ' || text_array_join(tags))
                       ) stored,
  created_at           timestamptz not null default now(),
  updated_at           timestamptz not null default now(),
  deleted_at           timestamptz
);
create index idx_contacts_workspace_status on contacts (workspace_id, status) where deleted_at is null;
create index idx_contacts_workspace_owner  on contacts (workspace_id, owner_user_id) where deleted_at is null;
create index idx_contacts_company          on contacts (company_id);
create index idx_contacts_search           on contacts using gin (search_vector);
create index idx_contacts_name_trgm        on contacts using gin (display_name extensions.gin_trgm_ops);
create index idx_contacts_next_due         on contacts (workspace_id, next_due_at) where deleted_at is null and status <> 'archived';

create table contact_facts (
  id             uuid primary key default gen_random_uuid(),
  workspace_id   uuid not null references workspaces(id) on delete cascade,
  contact_id     uuid not null references contacts(id) on delete cascade,
  category       fact_category not null,
  content        text not null check (length(content) between 1 and 500),
  confidence     real not null default 1.0 check (confidence between 0 and 1),
  source         fact_source not null default 'manual',
  source_interaction_id uuid,
  is_active      boolean not null default true,
  superseded_by  uuid references contact_facts(id),
  created_by     uuid not null references profiles(id),
  created_at     timestamptz not null default now(),
  updated_at     timestamptz not null default now()
);
create index idx_contact_facts_contact_active on contact_facts (contact_id) where is_active;

create table contact_profiles (
  contact_id           uuid primary key references contacts(id) on delete cascade,
  workspace_id         uuid not null references workspaces(id) on delete cascade,
  summary              text not null default '',
  communication_style  text,
  remember             text[] not null default '{}',
  risks                text[] not null default '{}',
  talking_points       text[] not null default '{}',
  common_ground        text[] not null default '{}',
  model                text,
  prompt_version       text,
  generated_at         timestamptz,
  stale                boolean not null default true,
  updated_at           timestamptz not null default now()
);

create table interactions (
  id               uuid primary key default gen_random_uuid(),
  workspace_id     uuid not null references workspaces(id) on delete cascade,
  contact_id       uuid references contacts(id) on delete cascade,
  user_id          uuid not null references profiles(id),
  kind             interaction_kind not null default 'note',
  direction        interaction_direction not null default 'mutual',
  occurred_at      timestamptz not null default now(),
  subject          text,
  body             text not null default '',
  summary          text,
  sentiment        sentiment_label,
  sentiment_score  real check (sentiment_score between -1 and 1),
  source           interaction_source not null default 'manual',
  external_id      text,
  ai_status        ai_status not null default 'none',
  ai_extraction    jsonb,
  metadata         jsonb not null default '{}'::jsonb,
  search_vector    tsvector generated always as (to_tsvector('english', coalesce(subject,'') || ' ' || coalesce(body,''))) stored,
  embedding        extensions.vector(1536),
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

create table captures (
  id             uuid primary key default gen_random_uuid(),
  workspace_id   uuid not null references workspaces(id) on delete cascade,
  user_id        uuid not null references profiles(id),
  contact_id     uuid references contacts(id) on delete set null,
  kind           text not null check (kind in ('voice', 'text')),
  storage_path   text,
  duration_seconds real,
  transcript     text,
  raw_text       text,
  status         capture_status not null default 'uploaded',
  proposal       jsonb,
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
  priority              smallint not null default 2 check (priority between 1 and 3),
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
  stage            text not null default 'qualifying',
  probability      smallint check (probability between 0 and 100),
  expected_close   date,
  status           opportunity_status not null default 'open',
  external_id      text,
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

create table contact_edges (
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
  check (contact_a_id < contact_b_id),
  unique (workspace_id, contact_a_id, contact_b_id)
);
create index idx_contact_edges_b on contact_edges (contact_b_id);

create table relationship_scores (
  id           uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references workspaces(id) on delete cascade,
  contact_id   uuid not null references contacts(id) on delete cascade,
  scored_on    date not null,
  score        smallint not null check (score between 0 and 100),
  components   jsonb not null,
  band         text not null check (band in ('strong','steady','weak','drifting')),
  created_at   timestamptz not null default now(),
  unique (contact_id, scored_on)
);
create index idx_relationship_scores_contact on relationship_scores (contact_id, scored_on desc);

create table insights (
  id               uuid primary key default gen_random_uuid(),
  workspace_id     uuid not null references workspaces(id) on delete cascade,
  user_id          uuid references profiles(id) on delete cascade,
  contact_id       uuid references contacts(id) on delete cascade,
  company_id       uuid references companies(id) on delete cascade,
  kind             insight_kind not null,
  severity         insight_severity not null default 'info',
  title            text not null,
  body             text not null,
  evidence         jsonb not null default '{}'::jsonb,
  suggested_action jsonb,
  dedupe_key       text not null,
  status           insight_status not null default 'new',
  expires_at       timestamptz,
  generated_by     text not null,
  created_at       timestamptz not null default now(),
  updated_at       timestamptz not null default now(),
  unique (workspace_id, dedupe_key)
);
create index idx_insights_user_status on insights (user_id, status, created_at desc);
create index idx_insights_workspace_status on insights (workspace_id, status, created_at desc);

create table context_items (
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
  credentials_enc      bytea,
  sync_cursor          jsonb not null default '{}'::jsonb,
  last_synced_at       timestamptz,
  last_error           text,
  created_at           timestamptz not null default now(),
  updated_at           timestamptz not null default now(),
  unique (user_id, provider)
);
