-- Read models. contact_overview and workspace_metrics inherit RLS via security_invoker.
-- member_directory is a definer view (profiles RLS only exposes the caller's own row) scoped by shared workspace.
create view contact_overview with (security_invoker = true) as
select c.*,
       co.name as company_name,
       co.industry as company_industry,
       (select count(*) from tasks t where t.contact_id = c.id and t.status = 'open')::int as open_task_count,
       (select coalesce(sum(o.value_cents), 0) from opportunity_contacts oc join opportunities o on o.id = oc.opportunity_id
          where oc.contact_id = c.id and o.status = 'open' and o.deleted_at is null)::bigint as open_opportunity_value_cents,
       (c.gravity_score - (select rs.score from relationship_scores rs where rs.contact_id = c.id
          and rs.scored_on <= current_date - 30 order by rs.scored_on desc limit 1))::int as score_delta_30d
from contacts c left join companies co on co.id = c.company_id
where c.deleted_at is null;

create view workspace_metrics with (security_invoker = true) as
select w.id as workspace_id,
       (select count(*) from contacts c where c.workspace_id = w.id and c.deleted_at is null and c.status <> 'archived')::int as contact_count,
       (select count(*) from contacts c where c.workspace_id = w.id and c.deleted_at is null and c.status <> 'archived'
          and c.last_interaction_at >= now() - interval '90 days')::int as active_90d,
       (select coalesce(round(avg(c.gravity_score)), 0) from contacts c where c.workspace_id = w.id and c.deleted_at is null and c.status <> 'archived')::int as avg_gravity,
       (select coalesce(sum(o.value_cents), 0) from opportunities o where o.workspace_id = w.id and o.status = 'open' and o.deleted_at is null)::bigint as pipeline_value,
       (select count(*) from contacts c where c.workspace_id = w.id and c.deleted_at is null and c.status <> 'archived'
          and c.next_due_at <= now() + interval '7 days')::int as due_count
from workspaces w;

create view member_directory as
select m.workspace_id, p.id as user_id, p.full_name, p.role_title, p.avatar_path, p.email, m.role, m.status, m.joined_at, m.departed_at
from memberships m join profiles p on p.id = m.user_id
where is_member(m.workspace_id, 'viewer');
