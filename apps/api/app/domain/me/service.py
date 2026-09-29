import time
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app import supabase_admin
from app.auth.jwt import AuthContext
from app.db.enums import MembershipStatus, WorkspaceKind
from app.db.repositories import profiles as profiles_repo
from app.db.repositories import workspaces as workspaces_repo
from app.domain.audit import write_audit
from app.domain.me.schemas import (
    InterestRead,
    MembershipRead,
    MeRead,
    MeUpdate,
    OnboardingUpdate,
    ProfileRead,
)
from app.errors import Problem


async def get_me(session: AsyncSession, user_id: UUID) -> MeRead:
    profile = await profiles_repo.get_profile(session, user_id)
    if profile is None:
        raise Problem(404, "not_found", "Profile not found", "Your profile has not been provisioned yet.")
    interests = await profiles_repo.list_interests(session, user_id)
    rows = await workspaces_repo.list_memberships(session, user_id)
    memberships = [
        MembershipRead(
            workspace_id=ws.id,
            workspace_name=ws.name,
            kind=ws.kind,
            slug=ws.slug,
            role=m.role,
            status=m.status,
            settings=ws.settings,
        )
        for m, ws in rows
    ]
    return MeRead(
        profile=ProfileRead.model_validate(profile),
        interests=[InterestRead.model_validate(i) for i in interests],
        memberships=memberships,
    )


async def update_me(session: AsyncSession, user_id: UUID, body: MeUpdate) -> MeRead:
    profile = await profiles_repo.get_profile(session, user_id)
    if profile is None:
        raise Problem(404, "not_found", "Profile not found")
    fields = body.model_dump(exclude_unset=True, exclude={"interests"})
    if "goals" in fields and fields["goals"] is not None:
        fields["goals"] = body.goals.model_dump() if body.goals else {}
    if "default_workspace_id" in fields and fields["default_workspace_id"] is not None:
        m = await workspaces_repo.get_membership(session, fields["default_workspace_id"], user_id)
        if m is None or m.status != "active":
            raise Problem(403, "not_a_member", "Not a member", "You are not an active member of that workspace.")
    await profiles_repo.update_profile(session, profile, fields)
    if body.interests is not None:
        await profiles_repo.replace_interests(session, user_id, [(i.kind, i.value) for i in body.interests])
    return await get_me(session, user_id)


async def update_onboarding(session: AsyncSession, user_id: UUID, body: OnboardingUpdate) -> MeRead:
    profile = await profiles_repo.get_profile(session, user_id)
    if profile is None:
        raise Problem(404, "not_found", "Profile not found")
    fields: dict[str, object] = {}
    if body.step == 1:
        if body.profile is None:
            raise Problem(422, "validation_error", "Invalid request", "Step 1 needs profile.")
        fields.update(body.profile.model_dump())
    elif body.step == 2:
        await profiles_repo.replace_interests(session, user_id, [(i.kind, i.value) for i in body.interests or []])
    elif body.step == 3:
        fields["goals"] = body.goals.model_dump() if body.goals else {}
    if body.step == 5:
        fields["onboarding_completed_at"] = datetime.now(UTC)
    fields["onboarding_step"] = max(profile.onboarding_step, body.step)
    await profiles_repo.update_profile(session, profile, fields)
    return await get_me(session, user_id)


FRESH_TOKEN_SECONDS = 300


async def delete_account(session: AsyncSession, ctx: AuthContext) -> None:
    """Section 6.6: requires a token issued in the last five minutes and, when MFA is enrolled, aal2. Departs every
    organization, deletes the personal workspace, tombstones the profile, then deletes the auth user."""
    issued = int(ctx.claims.get("iat", 0))
    if time.time() - issued > FRESH_TOKEN_SECONDS:
        raise Problem(
            403, "reauthentication_required", "Sign in again", "Deleting your account needs a sign-in from the last five minutes."
        )
    if ctx.aal != "aal2" and await supabase_admin.has_verified_mfa(ctx.user_id):
        raise Problem(
            403, "mfa_required", "Multi-factor authentication required", "Verify your second factor before deleting your account."
        )
    user_id = UUID(ctx.user_id)
    rows = await workspaces_repo.list_memberships(session, user_id)
    for m, ws in rows:
        if ws.kind == WorkspaceKind.organization and m.status == MembershipStatus.active:
            if m.role == "owner":
                others = await session.scalar(
                    text("select count(*) from memberships where workspace_id = :ws and status = 'active' and user_id <> :u"),
                    {"ws": ws.id, "u": user_id},
                )
                if others:
                    raise Problem(
                        409,
                        "conflict",
                        "Transfer ownership first",
                        f"You own {ws.name}. Transfer ownership or remove the other members before deleting your account.",
                    )
                await session.execute(text("delete from workspaces where id = :ws"), {"ws": ws.id})
                continue
            await workspaces_repo.depart(session, m)
            await write_audit(session, ws.id, "membership.depart", "membership", m.id, {"reason": "account_deleted"})
    for _m, ws in rows:
        if ws.kind == WorkspaceKind.personal:
            await session.execute(text("delete from workspaces where id = :ws"), {"ws": ws.id})
    await session.execute(text("delete from captures where user_id = :u"), {"u": user_id})
    await session.execute(text("select tombstone_me()"))
    await supabase_admin.delete_user(ctx.user_id)
