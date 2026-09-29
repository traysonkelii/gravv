from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.db.session import api_engine

router = APIRouter(tags=["health"])


@router.get("/healthz", operation_id="health_live")
async def health_live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/readyz", operation_id="health_ready")
async def health_ready() -> JSONResponse:
    try:
        async with api_engine().connect() as conn:
            # is_member() only exists once the migrations have been applied.
            ok = await conn.scalar(text("select to_regprocedure('public.is_member(uuid, workspace_role)') is not null"))
    except Exception:
        return JSONResponse({"status": "unavailable", "database": "unreachable"}, status_code=503)
    if not ok:
        return JSONResponse({"status": "unavailable", "database": "migrations missing"}, status_code=503)
    return JSONResponse({"status": "ok", "database": "ok"})
