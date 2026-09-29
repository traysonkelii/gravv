-- Triggers, helpers, search, and the job enqueue entry point.

-- Role helpers live here (not in the RLS migration) because enqueue_job depends on them.
create or replace function role_rank(r workspace_role) returns int language sql immutable as $$
  select case r when 'viewer' then 1 when 'member' then 2 when 'manager' then 3 when 'admin' then 4 when 'owner' then 5 end $$;

create or replace function is_member(ws uuid, min_role workspace_role default 'viewer')
returns boolean language sql stable security definer set search_path = public, extensions as $$
  select exists (
    select 1 from memberships m
    where m.workspace_id = ws and m.user_id = auth.uid() and m.status = 'active'
      and role_rank(m.role) >= role_rank(min_role))
$$;
revoke all on function is_member(uuid, workspace_role) from public;
grant execute on function is_member(uuid, workspace_role) to authenticated, service_role;

create or replace function set_updated_at() returns trigger language plpgsql as $$
begin new.updated_at = now(); return new; end $$;

do $$
declare t text;
begin
  foreach t in array array['profiles','workspaces','memberships','companies','contacts','contact_facts',
                           'contact_profiles','interactions','captures','tasks','opportunities','insights','integrations']
  loop
    execute format('create trigger trg_%s_updated_at before update on %I for each row execute function set_updated_at()', t, t);
  end loop;
end $$;

-- Trigger functions are security definer: a member may write an interaction on a teammate's
-- contact, and the denormalized update on contacts must not be blocked by the contacts policy.
create or replace function on_interaction_written() returns trigger
language plpgsql security definer set search_path = public, extensions as $$
begin
  if new.contact_id is not null and new.deleted_at is null then
    update contacts set last_interaction_at = greatest(coalesce(last_interaction_at, 'epoch'), new.occurred_at)
      where id = new.contact_id;
    update contact_profiles set stale = true where contact_id = new.contact_id;
  end if;
  return new;
end $$;
create trigger trg_interaction_written after insert or update of occurred_at, deleted_at, contact_id on interactions
  for each row execute function on_interaction_written();

create or replace function on_fact_written() returns trigger
language plpgsql security definer set search_path = public, extensions as $$
begin
  update contact_profiles set stale = true where contact_id = new.contact_id;
  return new;
end $$;
create trigger trg_fact_written after insert or update on contact_facts for each row execute function on_fact_written();

create or replace function on_contact_created() returns trigger
language plpgsql security definer set search_path = public, extensions as $$
begin
  insert into contact_profiles (contact_id, workspace_id) values (new.id, new.workspace_id) on conflict do nothing;
  return new;
end $$;
create trigger trg_contact_created after insert on contacts for each row execute function on_contact_created();

-- Fuzzy contact search used by /search and capture contact matching. Runs under the caller's RLS.
create or replace function search_contacts(ws uuid, q text, lim int default 20)
returns table (id uuid, display_name text, title text, company_name text, gravity_score smallint, rank real)
language sql stable set search_path = public, extensions as $$
  select c.id, c.display_name, c.title, co.name, c.gravity_score,
         greatest(similarity(c.display_name, q), ts_rank(c.search_vector, plainto_tsquery('simple', q))) as rank
  from contacts c left join companies co on co.id = c.company_id
  where c.workspace_id = ws and c.deleted_at is null
    and (c.display_name % q or c.search_vector @@ plainto_tsquery('simple', q) or co.name ilike '%' || q || '%')
  order by rank desc limit lim
$$;

-- Job enqueueing: authenticated never touches jobs directly.
create or replace function enqueue_job(p_kind text, p_payload jsonb, p_workspace_id uuid, p_run_after timestamptz default now(),
                                       p_priority smallint default 5, p_dedupe_key text default null)
returns uuid language plpgsql security definer set search_path = public, extensions as $$
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
grant execute on function enqueue_job(text, jsonb, uuid, timestamptz, smallint, text) to authenticated, service_role;

-- Sanitized job status for the owner of the job.
create or replace function get_job(p_id uuid)
returns table (id uuid, kind text, status job_status, result jsonb, last_error text, created_at timestamptz, finished_at timestamptz)
language sql stable security definer set search_path = public, extensions as $$
  select j.id, j.kind, j.status, j.result, j.last_error, j.created_at, j.finished_at
  from jobs j where j.id = p_id and j.user_id = auth.uid()
$$;
revoke all on function get_job(uuid) from public;
grant execute on function get_job(uuid) to authenticated;

-- Audit writes stay out of the caller's privileges.
create or replace function write_audit(p_workspace_id uuid, p_action text, p_entity_type text, p_entity_id uuid,
                                       p_diff jsonb default null, p_ip inet default null, p_user_agent text default null)
returns void language sql security definer set search_path = public, extensions as $$
  insert into audit_log (workspace_id, actor_user_id, action, entity_type, entity_id, diff, ip, user_agent)
  values (p_workspace_id, auth.uid(), p_action, p_entity_type, p_entity_id, p_diff, p_ip, p_user_agent)
$$;
revoke all on function write_audit(uuid, text, text, uuid, jsonb, inet, text) from public;
grant execute on function write_audit(uuid, text, text, uuid, jsonb, inet, text) to authenticated, service_role;

-- Organization creation inserts the workspace and the owner membership atomically.
create or replace function create_organization(p_name text, p_slug text default null, p_settings jsonb default '{}'::jsonb)
returns uuid language plpgsql security definer set search_path = public, extensions as $$
declare ws_id uuid;
begin
  if auth.uid() is null then raise exception 'unauthenticated' using errcode = '42501'; end if;
  insert into workspaces (kind, name, slug, owner_user_id, settings)
  values ('organization', p_name, nullif(p_slug, ''), auth.uid(), coalesce(p_settings, '{}'::jsonb)) returning id into ws_id;
  insert into memberships (workspace_id, user_id, role, status) values (ws_id, auth.uid(), 'owner', 'active');
  return ws_id;
end $$;
revoke all on function create_organization(text, text, jsonb) from public;
grant execute on function create_organization(text, text, jsonb) to authenticated;

-- Invitation preview (public) and acceptance (signed in, email must match).
create or replace function peek_invitation(p_token_hash text)
returns table (workspace_name text, role workspace_role, inviter_name text, email citext, expires_at timestamptz, accepted boolean)
language sql stable security definer set search_path = public, extensions as $$
  select w.name, i.role, p.full_name, i.email, i.expires_at, i.accepted_at is not null
  from invitations i join workspaces w on w.id = i.workspace_id join profiles p on p.id = i.invited_by
  where i.token_hash = p_token_hash
$$;
revoke all on function peek_invitation(text) from public;
grant execute on function peek_invitation(text) to anon, authenticated;

create or replace function accept_invitation(p_token_hash text)
returns uuid language plpgsql security definer set search_path = public, extensions as $$
declare inv invitations%rowtype; my_email citext;
begin
  select email into my_email from profiles where id = auth.uid();
  if my_email is null then raise exception 'unauthenticated' using errcode = '42501'; end if;
  select * into inv from invitations where token_hash = p_token_hash for update;
  if inv.id is null then raise exception 'invitation not found' using errcode = 'P0002'; end if;
  if inv.accepted_at is not null then raise exception 'invitation already accepted' using errcode = 'P0003'; end if;
  if inv.expires_at < now() then raise exception 'invitation expired' using errcode = 'P0004'; end if;
  if inv.email <> my_email then raise exception 'invitation email does not match' using errcode = '42501'; end if;
  insert into memberships (workspace_id, user_id, role, status)
  values (inv.workspace_id, auth.uid(), inv.role, 'active')
  on conflict (workspace_id, user_id) do update set role = excluded.role, status = 'active', departed_at = null, grace_until = null, joined_at = now();
  update invitations set accepted_at = now() where id = inv.id;
  return inv.workspace_id;
end $$;
revoke all on function accept_invitation(text) from public;
grant execute on function accept_invitation(text) to authenticated;
