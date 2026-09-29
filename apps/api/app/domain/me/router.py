from uuid import UUID

from fastapi import APIRouter

from app.auth.deps import CurrentUser, Session
from app.domain.me import service
from app.domain.me.schemas import MeRead, MeUpdate, OnboardingUpdate

router = APIRouter(prefix="/me", tags=["me"])


@router.get("", operation_id="me_get", response_model=MeRead)
async def me_get(ctx: CurrentUser, session: Session) -> MeRead:
    return await service.get_me(session, UUID(ctx.user_id))


@router.patch("", operation_id="me_update", response_model=MeRead)
async def me_update(body: MeUpdate, ctx: CurrentUser, session: Session) -> MeRead:
    return await service.update_me(session, UUID(ctx.user_id), body)


@router.patch("/onboarding", operation_id="me_onboarding_update", response_model=MeRead)
async def me_onboarding_update(body: OnboardingUpdate, ctx: CurrentUser, session: Session) -> MeRead:
    return await service.update_onboarding(session, UUID(ctx.user_id), body)
