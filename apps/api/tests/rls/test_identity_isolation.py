"""profiles: own row only. memberships: visible to members of the workspace; only admins insert."""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from tests.conftest import AuthAdmin, create_org, rls_session


async def test_profiles_are_private(auth_admin: AuthAdmin) -> None:
    a = await auth_admin.create_user("pa", "Pat A")
    b = await auth_admin.create_user("pb", "Pat B")
    async with rls_session(a) as s:
        emails = list(await s.scalars(text("select email from profiles")))
    assert emails == [a.email]
    async with rls_session(a) as s:
        updated = await s.execute(text("update profiles set full_name = 'Hijacked' where id = :b returning id"), {"b": b.id})
        assert updated.first() is None
    async with rls_session(b) as s:
        assert await s.scalar(text("select full_name from profiles where id = :b"), {"b": b.id}) == "Pat B"


async def test_member_directory_scoped_to_shared_workspaces(auth_admin: AuthAdmin) -> None:
    a = await auth_admin.create_user("da", "Dir A")
    b = await auth_admin.create_user("db", "Dir B")
    c = await auth_admin.create_user("dc", "Dir C")
    x = await create_org(a, "Dir X")
    async with rls_session(a) as s:
        await s.execute(
            text("insert into memberships (workspace_id, user_id, role) values (:ws, :u, 'member')"),
            {"ws": x, "u": b.id},
        )
    async with rls_session(b) as s:
        names = sorted(await s.scalars(text("select full_name from member_directory where workspace_id = :ws"), {"ws": x}))
    assert names == ["Dir A", "Dir B"]
    async with rls_session(c) as s:
        assert await s.scalar(text("select count(*) from member_directory where workspace_id = :ws"), {"ws": x}) == 0
        assert await s.scalar(text("select count(*) from memberships where workspace_id = :ws"), {"ws": x}) == 0


async def test_only_admins_insert_memberships(auth_admin: AuthAdmin) -> None:
    a = await auth_admin.create_user("ma", "Mem A")
    b = await auth_admin.create_user("mb", "Mem B")
    c = await auth_admin.create_user("mc", "Mem C")
    x = await create_org(a, "Mem X")
    async with rls_session(a) as s:
        await s.execute(
            text("insert into memberships (workspace_id, user_id, role) values (:ws, :u, 'member')"),
            {"ws": x, "u": b.id},
        )
    with pytest.raises(DBAPIError):
        async with rls_session(b) as s:
            await s.execute(
                text("insert into memberships (workspace_id, user_id, role) values (:ws, :u, 'member')"),
                {"ws": x, "u": c.id},
            )
    with pytest.raises(DBAPIError):
        async with rls_session(c) as s:
            await s.execute(
                text("insert into memberships (workspace_id, user_id, role) values (:ws, :u, 'admin')"),
                {"ws": x, "u": c.id},
            )
    # a member may only mark their own row departed, never promote themselves
    with pytest.raises(DBAPIError):
        async with rls_session(b) as s:
            await s.execute(
                text("update memberships set role = 'owner' where workspace_id = :ws and user_id = :u"),
                {"ws": x, "u": b.id},
            )
