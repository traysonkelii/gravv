from typing import Any
from uuid import UUID

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Profile, UserInterest


async def get_profile(session: AsyncSession, user_id: UUID) -> Profile | None:
    return await session.get(Profile, user_id)


async def update_profile(session: AsyncSession, profile: Profile, fields: dict[str, Any]) -> Profile:
    for key, value in fields.items():
        setattr(profile, key, value)
    await session.flush()
    await session.refresh(profile)
    return profile


async def list_interests(session: AsyncSession, user_id: UUID) -> list[UserInterest]:
    rows = await session.scalars(
        select(UserInterest).where(UserInterest.user_id == user_id).order_by(UserInterest.kind, UserInterest.value)
    )
    return list(rows)


async def replace_interests(session: AsyncSession, user_id: UUID, interests: list[tuple[str, str]]) -> None:
    await session.execute(delete(UserInterest).where(UserInterest.user_id == user_id))
    seen: set[tuple[str, str]] = set()
    for kind, value in interests:
        key = (kind, value.strip().lower())
        if not value.strip() or key in seen:
            continue
        seen.add(key)
        session.add(UserInterest(user_id=user_id, kind=kind, value=value.strip()))
    await session.flush()


async def tombstone_profile(session: AsyncSession, user_id: UUID) -> None:
    await session.execute(
        text(
            "update profiles set deleted_at = now(), full_name = 'Former member', role_title = null, "
            "avatar_path = null, goals = '{}'::jsonb, email = :email where id = :id"
        ),
        {"id": user_id, "email": f"deleted-{user_id}@tombstone.gravv.local"},
    )
