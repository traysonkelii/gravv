-- Row Level Security on every table in public. The API runs as `authenticated` with request.jwt.claims set.
do $$
declare t text;
begin
  foreach t in array array['profiles','user_interests','workspaces','memberships','invitations','companies','contacts',
    'contact_facts','contact_profiles','interactions','captures','tasks','opportunities','opportunity_contacts',
    'contact_edges','relationship_scores','insights','context_items','integrations','jobs','audit_log','exports']
  loop
    execute format('alter table %I enable row level security', t);
  end loop;
end $$;

-- profiles: own row only. Teammates are visible through member_directory.
create policy profiles_select on profiles for select to authenticated using (id = auth.uid());
create policy profiles_update on profiles for update to authenticated using (id = auth.uid()) with check (id = auth.uid());

create policy user_interests_all on user_interests for all to authenticated
  using (user_id = auth.uid()) with check (user_id = auth.uid());

-- workspaces
create policy workspaces_select on workspaces for select to authenticated using (is_member(id, 'viewer'));
create policy workspaces_insert on workspaces for insert to authenticated
  with check (owner_user_id = auth.uid() and kind = 'organization');
create policy workspaces_update on workspaces for update to authenticated
  using (is_member(id, 'admin')) with check (is_member(id, 'admin'));
create policy workspaces_delete on workspaces for delete to authenticated using (owner_user_id = auth.uid());

-- memberships
create policy memberships_select on memberships for select to authenticated
  using (user_id = auth.uid() or is_member(workspace_id, 'member'));
create policy memberships_insert on memberships for insert to authenticated
  with check (
    is_member(workspace_id, 'admin')
    or (user_id = auth.uid() and role = 'owner'
        and exists (select 1 from workspaces w where w.id = workspace_id and w.owner_user_id = auth.uid()))
  );
create policy memberships_update on memberships for update to authenticated
  using (is_member(workspace_id, 'admin') or user_id = auth.uid())
  with check (is_member(workspace_id, 'admin') or (user_id = auth.uid() and status = 'departed'));
create policy memberships_delete on memberships for delete to authenticated using (is_member(workspace_id, 'admin'));

-- invitations: admins only; peek/accept go through security definer functions.
create policy invitations_all on invitations for all to authenticated
  using (is_member(workspace_id, 'admin')) with check (is_member(workspace_id, 'admin') and invited_by = auth.uid());

-- companies
-- Soft-deleted rows stay visible to policies: Postgres re-checks the select policy against the updated row,
-- so `deleted_at is null` here would block soft deletes. Every read query and view filters deleted_at instead.
create policy companies_select on companies for select to authenticated
  using (is_member(workspace_id, 'viewer'));
create policy companies_insert on companies for insert to authenticated
  with check (is_member(workspace_id, 'member') and created_by = auth.uid());
create policy companies_update on companies for update to authenticated
  using (is_member(workspace_id, 'member')) with check (is_member(workspace_id, 'member'));
create policy companies_delete on companies for delete to authenticated using (is_member(workspace_id, 'admin'));

-- contacts
create policy contacts_select on contacts for select to authenticated using (
  is_member(workspace_id, 'viewer')
  and (visibility = 'team' or owner_user_id = auth.uid())
);
create policy contacts_insert on contacts for insert to authenticated with check (
  is_member(workspace_id, 'member') and owner_user_id = auth.uid()
);
create policy contacts_update on contacts for update to authenticated using (
  is_member(workspace_id, 'member')
  and (owner_user_id = auth.uid() or is_member(workspace_id, 'manager'))
) with check (
  is_member(workspace_id, 'member')
);
create policy contacts_delete on contacts for delete to authenticated using (
  owner_user_id = auth.uid() or is_member(workspace_id, 'admin')
);

-- child tables follow the parent contact's visibility by re-using the contacts policy through exists()
create policy contact_facts_select on contact_facts for select to authenticated
  using (is_member(workspace_id, 'viewer') and exists (select 1 from contacts c where c.id = contact_id));
create policy contact_facts_insert on contact_facts for insert to authenticated
  with check (is_member(workspace_id, 'member') and created_by = auth.uid() and exists (select 1 from contacts c where c.id = contact_id));
create policy contact_facts_update on contact_facts for update to authenticated
  using (is_member(workspace_id, 'member') and exists (select 1 from contacts c where c.id = contact_id))
  with check (is_member(workspace_id, 'member'));
create policy contact_facts_delete on contact_facts for delete to authenticated
  using (is_member(workspace_id, 'member') and exists (select 1 from contacts c where c.id = contact_id));

create policy contact_profiles_select on contact_profiles for select to authenticated
  using (is_member(workspace_id, 'viewer') and exists (select 1 from contacts c where c.id = contact_id));
create policy contact_profiles_write on contact_profiles for all to authenticated
  using (is_member(workspace_id, 'member') and exists (select 1 from contacts c where c.id = contact_id))
  with check (is_member(workspace_id, 'member'));

create policy interactions_select on interactions for select to authenticated using (
  is_member(workspace_id, 'viewer')
  and ((contact_id is null and user_id = auth.uid()) or exists (select 1 from contacts c where c.id = contact_id))
);
create policy interactions_insert on interactions for insert to authenticated
  with check (is_member(workspace_id, 'member') and user_id = auth.uid()
              and (contact_id is null or exists (select 1 from contacts c where c.id = contact_id)));
create policy interactions_update on interactions for update to authenticated
  using (is_member(workspace_id, 'member') and (user_id = auth.uid() or is_member(workspace_id, 'manager')))
  with check (is_member(workspace_id, 'member'));
create policy interactions_delete on interactions for delete to authenticated
  using (user_id = auth.uid() or is_member(workspace_id, 'manager'));

create policy captures_all on captures for all to authenticated
  using (user_id = auth.uid() and is_member(workspace_id, 'member'))
  with check (user_id = auth.uid() and is_member(workspace_id, 'member'));

create policy tasks_select on tasks for select to authenticated
  using (is_member(workspace_id, 'viewer') and (contact_id is null or exists (select 1 from contacts c where c.id = contact_id)));
create policy tasks_insert on tasks for insert to authenticated
  with check (is_member(workspace_id, 'member') and created_by = auth.uid()
              and (contact_id is null or exists (select 1 from contacts c where c.id = contact_id)));
create policy tasks_update on tasks for update to authenticated
  using (is_member(workspace_id, 'member')) with check (is_member(workspace_id, 'member'));
create policy tasks_delete on tasks for delete to authenticated
  using (is_member(workspace_id, 'member') and (created_by = auth.uid() or assignee_user_id = auth.uid() or is_member(workspace_id, 'manager')));

create policy opportunities_select on opportunities for select to authenticated
  using (is_member(workspace_id, 'viewer'));
create policy opportunities_insert on opportunities for insert to authenticated
  with check (is_member(workspace_id, 'member') and owner_user_id = auth.uid());
create policy opportunities_update on opportunities for update to authenticated
  using (is_member(workspace_id, 'member')) with check (is_member(workspace_id, 'member'));
create policy opportunities_delete on opportunities for delete to authenticated
  using (owner_user_id = auth.uid() or is_member(workspace_id, 'admin'));

create policy opportunity_contacts_select on opportunity_contacts for select to authenticated
  using (exists (select 1 from opportunities o where o.id = opportunity_id));
create policy opportunity_contacts_write on opportunity_contacts for all to authenticated
  using (exists (select 1 from opportunities o where o.id = opportunity_id and is_member(o.workspace_id, 'member')))
  with check (exists (select 1 from opportunities o where o.id = opportunity_id and is_member(o.workspace_id, 'member'))
              and exists (select 1 from contacts c where c.id = contact_id));

create policy contact_edges_select on contact_edges for select to authenticated
  using (is_member(workspace_id, 'viewer')
         and exists (select 1 from contacts c where c.id = contact_a_id)
         and exists (select 1 from contacts c where c.id = contact_b_id));
create policy contact_edges_insert on contact_edges for insert to authenticated
  with check (is_member(workspace_id, 'member') and created_by = auth.uid()
              and exists (select 1 from contacts c where c.id = contact_a_id)
              and exists (select 1 from contacts c where c.id = contact_b_id));
create policy contact_edges_delete on contact_edges for delete to authenticated
  using (is_member(workspace_id, 'member'));
-- upserting a reverse-order edge takes the ON CONFLICT DO UPDATE path
create policy contact_edges_update on contact_edges for update to authenticated
  using (is_member(workspace_id, 'member')) with check (is_member(workspace_id, 'member'));

create policy relationship_scores_select on relationship_scores for select to authenticated
  using (is_member(workspace_id, 'viewer') and exists (select 1 from contacts c where c.id = contact_id));
create policy relationship_scores_write on relationship_scores for all to authenticated
  using (is_member(workspace_id, 'member')) with check (is_member(workspace_id, 'member') and exists (select 1 from contacts c where c.id = contact_id));

create policy insights_select on insights for select to authenticated using (
  is_member(workspace_id, 'viewer')
  and (user_id = auth.uid() or (user_id is null and is_member(workspace_id, 'manager')))
  and (contact_id is null or exists (select 1 from contacts c where c.id = contact_id))
);
create policy insights_write on insights for all to authenticated
  using (is_member(workspace_id, 'member') and (user_id = auth.uid() or (user_id is null and is_member(workspace_id, 'manager'))))
  with check (is_member(workspace_id, 'member'));

create policy context_items_select on context_items for select to authenticated using (is_member(workspace_id, 'viewer'));
create policy context_items_write on context_items for all to authenticated
  using (is_member(workspace_id, 'member')) with check (is_member(workspace_id, 'member'));

create policy integrations_all on integrations for all to authenticated
  using (user_id = auth.uid()) with check (user_id = auth.uid() and is_member(workspace_id, 'member'));

-- exports: the owner may create and read their own rows; the worker fills them in.
create policy exports_select on exports for select to authenticated using (user_id = auth.uid());
create policy exports_insert on exports for insert to authenticated
  with check (user_id = auth.uid() and is_member(workspace_id, 'viewer'));

-- jobs and audit_log: no policies for authenticated (deny all); reached only through security definer functions.

-- grants
revoke all on all tables in schema public from anon;
revoke all on all functions in schema public from anon;
grant usage on schema public to authenticated, anon;
grant select, insert, update, delete on all tables in schema public to authenticated;
alter default privileges in schema public grant select, insert, update, delete on tables to authenticated;
-- Column privileges only bite once the table-level grant is gone, so re-grant every column but credentials_enc.
revoke select on integrations from authenticated;
grant select (id, workspace_id, user_id, provider, status, external_account_id, scopes, sync_cursor,
              last_synced_at, last_error, created_at, updated_at) on integrations to authenticated;
grant execute on function peek_invitation(text) to anon;
