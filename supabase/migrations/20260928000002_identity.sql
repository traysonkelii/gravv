-- Identity and tenancy: profiles, interests, workspaces, memberships, invitations.
create table profiles (
  id                       uuid primary key references auth.users(id) on delete cascade,
  email                    citext not null unique,
  full_name                text not null default '',
  role_title               text,
  timezone                 text not null default 'UTC',
  avatar_path              text,
  goals                    jsonb not null default '{}'::jsonb,
  onboarding_step          smallint not null default 0,
  onboarding_completed_at  timestamptz,
  default_workspace_id     uuid,
  deleted_at               timestamptz,
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
  slug           citext unique,
  owner_user_id  uuid not null references profiles(id),
  settings       jsonb not null default '{}'::jsonb,
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
  token_hash    text not null unique,
  invited_by    uuid not null references profiles(id),
  expires_at    timestamptz not null default now() + interval '7 days',
  accepted_at   timestamptz,
  created_at    timestamptz not null default now()
);
create index idx_invitations_workspace_email on invitations (workspace_id, email);

-- Provision profile + personal workspace + owner membership for every new auth user.
create or replace function public.handle_new_user()
returns trigger language plpgsql security definer set search_path = public, extensions as $$
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
