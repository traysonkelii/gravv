"""Pure SQL through RLS-bound sessions. A owns org X, B owns org Y, C is a viewer in X."""

import uuid
from dataclasses import dataclass

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from tests.conftest import AuthAdmin, AuthUser, create_org, rls_session


@dataclass(frozen=True)
class Actors:
    a: AuthUser
    b: AuthUser
    c: AuthUser
    x: uuid.UUID
    y: uuid.UUID
    team: uuid.UUID
    private: uuid.UUID


@pytest.fixture(scope="module")
async def actors(auth_admin: AuthAdmin) -> Actors:
    a = await auth_admin.create_user("a", "Alice Owner")
    b = await auth_admin.create_user("b", "Bob Owner")
    c = await auth_admin.create_user("c", "Cara Viewer")
    x = await create_org(a, "Org X")
    y = await create_org(b, "Org Y")
    async with rls_session(a) as s:
        await s.execute(
            text("insert into memberships (workspace_id, user_id, role) values (:ws, :u, 'viewer')"),
            {"ws": x, "u": c.id},
        )
        team = await s.scalar(
            text(
                "insert into contacts (workspace_id, owner_user_id, first_name, last_name, visibility) "
                "values (:ws, :u, 'Team', 'Contact', 'team') returning id"
            ),
            {"ws": x, "u": a.id},
        )
        private = await s.scalar(
            text(
                "insert into contacts (workspace_id, owner_user_id, first_name, last_name, visibility) "
                "values (:ws, :u, 'Private', 'Contact', 'private') returning id"
            ),
            {"ws": x, "u": a.id},
        )
    return Actors(a=a, b=b, c=c, x=x, y=y, team=team, private=private)


async def _count_contacts(user: AuthUser, ws: str) -> int:
    async with rls_session(user) as s:
        return int(await s.scalar(text("select count(*) from contacts where workspace_id = :ws"), {"ws": ws}) or 0)


async def test_no_cross_workspace_reads(actors: Actors) -> None:
    assert await _count_contacts(actors.b, str(actors.x)) == 0
    assert await _count_contacts(actors.a, str(actors.x)) == 2


async def test_private_contact_invisible_to_teammate(actors: Actors) -> None:
    async with rls_session(actors.c) as s:
        names = list(await s.scalars(text("select display_name from contacts where workspace_id = :ws"), {"ws": actors.x}))
    assert names == ["Team Contact"]


async def test_viewer_cannot_insert(actors: Actors) -> None:
    with pytest.raises(DBAPIError):
        async with rls_session(actors.c) as s:
            await s.execute(
                text("insert into contacts (workspace_id, owner_user_id, first_name) values (:ws, :u, 'Nope')"),
                {"ws": actors.x, "u": actors.c.id},
            )


async def test_outsider_cannot_insert_into_foreign_workspace(actors: Actors) -> None:
    with pytest.raises(DBAPIError):
        async with rls_session(actors.b) as s:
            await s.execute(
                text("insert into contacts (workspace_id, owner_user_id, first_name) values (:ws, :u, 'Nope')"),
                {"ws": actors.x, "u": actors.b.id},
            )


async def test_departed_member_loses_access_instantly(actors: Actors, auth_admin: AuthAdmin) -> None:
    a = actors.a
    d = await auth_admin.create_user("d", "Dave Departing")
    async with rls_session(a) as s:
        await s.execute(
            text("insert into memberships (workspace_id, user_id, role) values (:ws, :u, 'member')"),
            {"ws": actors.x, "u": d.id},
        )
    assert await _count_contacts(d, str(actors.x)) == 1
    async with rls_session(a) as s:
        await s.execute(
            text("update memberships set status = 'departed', departed_at = now() where workspace_id = :ws and user_id = :u"),
            {"ws": actors.x, "u": d.id},
        )
    assert await _count_contacts(d, str(actors.x)) == 0


async def test_jobs_and_credentials_unreadable(actors: Actors) -> None:
    a = actors.a
    async with rls_session(a) as s:
        job_id = await s.scalar(text("select enqueue_job('noop', '{}'::jsonb, :ws)"), {"ws": actors.x})
        assert job_id is not None
        assert await s.scalar(text("select count(*) from jobs")) == 0
        visible = (await s.execute(text("select * from get_job(:id)"), {"id": job_id})).first()
        assert visible is not None and visible[2] == "queued"
    with pytest.raises(DBAPIError):
        async with rls_session(a) as s:
            await s.execute(text("select credentials_enc from integrations"))


async def test_anon_sees_nothing(actors: Actors) -> None:
    with pytest.raises(DBAPIError):
        async with rls_session(None) as s:
            await s.execute(text("select count(*) from contacts"))
