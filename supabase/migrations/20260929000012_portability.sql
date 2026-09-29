-- Data portability and account deletion (Section 6.6, M6).

-- Profiles outlive auth users: organization records keep created_by / owner_user_id pointing at a tombstone
-- profile after the auth user is deleted, so the cascade from auth.users is removed.
alter table profiles drop constraint profiles_id_fkey;

-- Exports may be created for a departing member by an admin, so creation goes through a definer function.
create or replace function create_export(p_workspace_id uuid, p_user_id uuid, p_scope text)
returns uuid language plpgsql security definer set search_path = public, extensions as $$
declare export_id uuid;
begin
  if p_scope not in ('personal', 'my_contributions', 'workspace') then
    raise exception 'unknown export scope %', p_scope using errcode = '22023';
  end if;
  if p_user_id <> auth.uid() and not is_member(p_workspace_id, 'admin') then
    raise exception 'only admins may export for another member' using errcode = '42501';
  end if;
  if p_user_id = auth.uid() and p_scope <> 'workspace' and not exists (
      select 1 from memberships m where m.workspace_id = p_workspace_id and m.user_id = auth.uid()) then
    raise exception 'not a member of workspace %', p_workspace_id using errcode = '42501';
  end if;
  if p_scope = 'workspace' and not is_member(p_workspace_id, 'admin') then
    raise exception 'workspace exports require the admin role' using errcode = '42501';
  end if;
  insert into exports (workspace_id, user_id, scope) values (p_workspace_id, p_user_id, p_scope) returning id into export_id;
  return export_id;
end $$;
revoke all on function create_export(uuid, uuid, text) from public;
grant execute on function create_export(uuid, uuid, text) to authenticated, service_role;

-- Tombstone the caller's own profile: personal identifiers go, the row stays for organization records.
create or replace function tombstone_me()
returns void language plpgsql security definer set search_path = public, extensions as $$
begin
  if auth.uid() is null then raise exception 'unauthenticated' using errcode = '42501'; end if;
  delete from user_interests where user_id = auth.uid();
  update profiles set deleted_at = now(), full_name = 'Former member', role_title = null, avatar_path = null,
    goals = '{}'::jsonb, timezone = 'UTC', default_workspace_id = null,
    email = 'deleted-' || auth.uid()::text || '@tombstone.gravv.local'
  where id = auth.uid();
end $$;
revoke all on function tombstone_me() from public;
grant execute on function tombstone_me() to authenticated;

alter table exports add column if not exists error text;
alter table exports add column if not exists finished_at timestamptz;
