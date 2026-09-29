-- Score writes go through a security definer function: a member may log a note on a teammate's contact and
-- the immediate rescore must update that contact row even though the contacts update policy would block it.
create or replace function apply_score(p_contact_id uuid, p_score smallint, p_band text, p_status contact_status,
                                       p_next_due_at timestamptz, p_components jsonb, p_scored_on date default current_date)
returns void language plpgsql security definer set search_path = public, extensions as $$
declare ws uuid;
begin
  select workspace_id into ws from contacts where id = p_contact_id and deleted_at is null;
  if ws is null then raise exception 'contact not found' using errcode = 'P0002'; end if;
  if auth.uid() is not null and not is_member(ws, 'member') then
    raise exception 'not a member of workspace %', ws using errcode = '42501';
  end if;
  insert into relationship_scores (workspace_id, contact_id, scored_on, score, components, band)
  values (ws, p_contact_id, p_scored_on, p_score, p_components, p_band)
  on conflict (contact_id, scored_on) do update set score = excluded.score, components = excluded.components, band = excluded.band;
  update contacts set gravity_score = p_score, gravity_updated_at = now(), next_due_at = p_next_due_at,
    status = case when status = 'archived' then status else p_status end
  where id = p_contact_id;
end $$;
revoke all on function apply_score(uuid, smallint, text, contact_status, timestamptz, jsonb, date) from public;
grant execute on function apply_score(uuid, smallint, text, contact_status, timestamptz, jsonb, date) to authenticated, service_role;

-- Insights are written by the worker; acting on one from the API needs the caller's identity only.
create index if not exists idx_relationship_scores_ws_day on relationship_scores (workspace_id, scored_on desc);
