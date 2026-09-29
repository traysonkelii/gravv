from collections import defaultdict, deque
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import WorkspaceContext
from app.db.repositories import contacts as contacts_repo
from app.domain.audit import write_audit
from app.domain.network.schemas import EdgeCreate, EdgeRead, Graph, GraphEdge, GraphNode, Path, PathsResult
from app.errors import Problem
from app.scoring.bands import BAND_SQL

_EDGES_FOR = text("""
select e.id, e.contact_a_id, e.contact_b_id, e.kind::text, e.strength, e.note, e.created_at,
       o.display_name, o.honorific, co.name as company, o.gravity_score
from contact_edges e
join contacts o on o.id = case when e.contact_a_id = :id then e.contact_b_id else e.contact_a_id end and o.deleted_at is null
left join companies co on co.id = o.company_id
where (e.contact_a_id = :id or e.contact_b_id = :id) and e.workspace_id = :ws
order by e.strength desc
""")


def _initials(name: str) -> str:
    parts = [p for p in name.split() if p and not p.endswith(".")]
    if not parts:
        return "?"
    return (parts[0][0] + (parts[-1][0] if len(parts) > 1 else "")).upper()


async def list_edges(session: AsyncSession, ws: WorkspaceContext, contact_id: UUID) -> list[EdgeRead]:
    if await contacts_repo.get_contact(session, ws.workspace_id, contact_id) is None:
        raise Problem(404, "not_found", "Contact not found")
    rows = (await session.execute(_EDGES_FOR, {"id": contact_id, "ws": ws.workspace_id})).mappings().all()
    return [
        EdgeRead(
            id=r["id"],
            contact_id=contact_id,
            other_contact_id=r["contact_b_id"] if r["contact_a_id"] == contact_id else r["contact_a_id"],
            other_display_name=r["display_name"],
            other_honorific=r["honorific"],
            other_company=r["company"],
            other_gravity_score=r["gravity_score"],
            kind=r["kind"],
            strength=r["strength"],
            note=r["note"],
            created_at=r["created_at"],
        )
        for r in rows
    ]


async def create_edge(session: AsyncSession, ws: WorkspaceContext, user_id: UUID, contact_id: UUID, body: EdgeCreate) -> EdgeRead:
    if contact_id == body.other_contact_id:
        raise Problem(422, "validation_error", "Invalid request", "A contact cannot be linked to itself.")
    for cid in (contact_id, body.other_contact_id):
        if await contacts_repo.get_contact(session, ws.workspace_id, cid) is None:
            raise Problem(404, "not_found", "Contact not found")
    a, b = sorted([contact_id, body.other_contact_id], key=str)
    edge_id = await session.scalar(
        text(
            "insert into contact_edges (workspace_id, contact_a_id, contact_b_id, kind, strength, note, created_by) "
            "values (:ws, :a, :b, cast(:kind as edge_kind), :strength, :note, :u) "
            "on conflict (workspace_id, contact_a_id, contact_b_id) do update set kind = excluded.kind, strength = excluded.strength, "
            "note = coalesce(excluded.note, contact_edges.note) returning id"
        ),
        {"ws": ws.workspace_id, "a": a, "b": b, "kind": body.kind.value, "strength": body.strength, "note": body.note, "u": user_id},
    )
    await write_audit(session, ws.workspace_id, "edge.create", "contact_edge", edge_id, {"a": str(a), "b": str(b)})
    edges = await list_edges(session, ws, contact_id)
    return next(e for e in edges if e.id == edge_id)


async def delete_edge(session: AsyncSession, ws: WorkspaceContext, edge_id: UUID) -> None:
    res = await session.execute(
        text("delete from contact_edges where id = :id and workspace_id = :ws returning id"), {"id": edge_id, "ws": ws.workspace_id}
    )
    if res.first() is None:
        raise Problem(404, "not_found", "Connection not found")
    await write_audit(session, ws.workspace_id, "edge.delete", "contact_edge", edge_id)


async def graph(
    session: AsyncSession,
    ws: WorkspaceContext,
    user_id: UUID,
    user_name: str,
    relationship_type: str | None,
    industry: str | None,
    min_score: int,
) -> Graph:
    params: dict[str, Any] = {"ws": ws.workspace_id, "min": min_score}
    where = ["c.workspace_id = :ws", "c.deleted_at is null", "c.status <> 'archived'", "c.gravity_score >= :min"]
    if relationship_type:
        where.append("c.relationship_type = cast(:rel as relationship_type)")
        params["rel"] = relationship_type
    if industry:
        where.append("lower(co.industry) = lower(:industry)")
        params["industry"] = industry
    band = BAND_SQL.format(t="c")
    rows = (
        (
            await session.execute(
                text(f"""
        select c.id, c.honorific, c.display_name, c.title, co.name as company, co.industry, c.relationship_type::text,
               c.gravity_score, {band} as band, c.last_interaction_at,
               (select coalesce(sum(o.value_cents), 0) from opportunity_contacts oc join opportunities o on o.id = oc.opportunity_id
                  where oc.contact_id = c.id and o.status = 'open' and o.deleted_at is null) as deal_value
        from contacts c left join companies co on co.id = c.company_id where {" and ".join(where)}
        """),
                params,
            )
        )
        .mappings()
        .all()
    )
    ids = {str(r["id"]) for r in rows}
    edge_rows = (
        await session.execute(
            text("select id, contact_a_id, contact_b_id, kind::text, strength from contact_edges where workspace_id = :ws"),
            {"ws": ws.workspace_id},
        )
    ).all()
    counts: dict[str, int] = defaultdict(int)
    edges: list[GraphEdge] = []
    for eid, a, b, kind, strength in edge_rows:
        if str(a) in ids and str(b) in ids:
            edges.append(GraphEdge(id=str(eid), source=str(a), target=str(b), strength=strength, kind=kind))
            counts[str(a)] += 1
            counts[str(b)] += 1
    nodes = [
        GraphNode(
            id="me",
            kind="me",
            display_name=user_name or "You",
            initials=_initials(user_name or "You"),
            title=None,
            company=None,
            industry=None,
            relationship_type=None,
            gravity_score=100,
            band="strong",
            last_interaction_at=None,
            deal_value_cents=0,
            connection_count=len(rows),
        )
    ]
    for r in rows:
        cid = str(r["id"])
        name = f"{r['honorific'] + ' ' if r['honorific'] else ''}{r['display_name']}"
        nodes.append(
            GraphNode(
                id=cid,
                kind="contact",
                display_name=name,
                initials=_initials(r["display_name"]),
                title=r["title"],
                company=r["company"],
                industry=r["industry"],
                relationship_type=r["relationship_type"],
                gravity_score=r["gravity_score"],
                band=r["band"],
                last_interaction_at=r["last_interaction_at"],
                deal_value_cents=int(r["deal_value"]),
                connection_count=counts[cid] + 1,
            )
        )
        edges.append(GraphEdge(id=f"me-{cid}", source="me", target=cid, strength=max(r["gravity_score"], 1), kind="knows"))
    return Graph(nodes=nodes, edges=edges)


async def paths(session: AsyncSession, ws: WorkspaceContext, user_id: UUID, user_name: str, from_: str, to: str) -> PathsResult:
    g = await graph(session, ws, user_id, user_name, None, None, 0)
    node_ids = {n.id for n in g.nodes}
    company_targets = [n.id for n in g.nodes if n.kind == "contact" and (str(n.company or "").lower() == to.lower())]
    company_row = (
        (
            await session.execute(
                text("select name from companies where id = cast(:id as uuid) and workspace_id = :ws"), {"id": to, "ws": ws.workspace_id}
            )
        ).first()
        if len(to) == 36 and to not in node_ids
        else None
    )
    if company_row:
        company_targets = [n.id for n in g.nodes if n.kind == "contact" and n.company == company_row[0]]
    targets = [to] if to in node_ids else company_targets
    if from_ not in node_ids:
        raise Problem(404, "not_found", "Start not found")
    if not targets:
        raise Problem(404, "not_found", "Target not found", "No contact or company matches the target.")
    adjacency: dict[str, list[tuple[str, int]]] = defaultdict(list)
    for e in g.edges:
        adjacency[e.source].append((e.target, e.strength))
        adjacency[e.target].append((e.source, e.strength))
    found: list[Path] = []
    target_set = set(targets) - {from_}
    # bounded breadth-first enumeration: all simple paths up to 4 hops, shortest first
    queue: deque[tuple[list[str], int]] = deque([([from_], 100)])
    while queue and len(found) < 25:
        path, min_strength = queue.popleft()
        if len(path) > 5:
            continue
        last = path[-1]
        if last in target_set and len(path) > 1:
            found.append(Path(nodes=path, hops=len(path) - 1, min_strength=min_strength))
            continue
        for nxt, strength in adjacency[last]:
            if nxt in path or (nxt == "me" and from_ != "me"):
                continue
            queue.append(([*path, nxt], min(min_strength, strength)))
    found.sort(key=lambda p: (p.hops, -p.min_strength))
    return PathsResult(from_id=from_, to_ids=targets, paths=found[:3])
