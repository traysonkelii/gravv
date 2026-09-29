from uuid import UUID

from fastapi import APIRouter, Response

from app.auth.deps import CurrentUser, Session
from app.domain.me import service
from app.domain.me.schemas import MeRead, MeUpdate, OnboardingUpdate
from app.domain.me.service import delete_account

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


@router.delete("", operation_id="me_delete", status_code=204)
async def me_delete(ctx: CurrentUser, session: Session) -> Response:
    await delete_account(session, ctx)
    return Response(status_code=204)
