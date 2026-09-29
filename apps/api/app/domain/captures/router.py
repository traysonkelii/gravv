from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from app.auth.deps import CurrentUser, Session, WorkspaceContext, require_role
from app.domain.captures import service
from app.domain.captures.schemas import (
    CaptureConfirm,
    CaptureRead,
    CaptureTextCreate,
    ConfirmResult,
    UploadedRequest,
    VoiceUploadRequest,
    VoiceUploadResponse,
)

router = APIRouter(prefix="/captures", tags=["captures"])
Member = Annotated[WorkspaceContext, Depends(require_role("member"))]


@router.post("/text", operation_id="captures_create_text", response_model=CaptureRead, status_code=202)
async def captures_create_text(body: CaptureTextCreate, ctx: CurrentUser, ws: Member, session: Session) -> CaptureRead:
    return await service.create_text(session, ws, UUID(ctx.user_id), body)


@router.post("/voice/upload-url", operation_id="captures_voice_upload_url", response_model=VoiceUploadResponse)
async def captures_voice_upload_url(body: VoiceUploadRequest, ctx: CurrentUser, ws: Member, session: Session) -> VoiceUploadResponse:
    return await service.voice_upload_url(session, ws, UUID(ctx.user_id), body)


@router.post("/{capture_id}/uploaded", operation_id="captures_voice_uploaded", response_model=CaptureRead, status_code=202)
async def captures_voice_uploaded(capture_id: UUID, body: UploadedRequest, ctx: CurrentUser, ws: Member, session: Session) -> CaptureRead:
    return await service.uploaded(session, ws, UUID(ctx.user_id), capture_id, body)


@router.get("", operation_id="captures_list", response_model=list[CaptureRead])
async def captures_list(ctx: CurrentUser, ws: Member, session: Session) -> list[CaptureRead]:
    return await service.list_pending(session, ws, UUID(ctx.user_id))


@router.get("/{capture_id}", operation_id="captures_get", response_model=CaptureRead)
async def captures_get(capture_id: UUID, ctx: CurrentUser, ws: Member, session: Session) -> CaptureRead:
    return await service.get(session, ws, UUID(ctx.user_id), capture_id)


@router.post("/{capture_id}/confirm", operation_id="captures_confirm", response_model=ConfirmResult)
async def captures_confirm(capture_id: UUID, body: CaptureConfirm, ctx: CurrentUser, ws: Member, session: Session) -> ConfirmResult:
    return await service.confirm(session, ws, UUID(ctx.user_id), capture_id, body)


@router.post("/{capture_id}/discard", operation_id="captures_discard", response_model=CaptureRead)
async def captures_discard(capture_id: UUID, ctx: CurrentUser, ws: Member, session: Session) -> CaptureRead:
    return await service.discard(session, ws, UUID(ctx.user_id), capture_id)
