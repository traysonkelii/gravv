from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.domain.health.router import router as health_router
from app.domain.invitations.router import router as invitations_router
from app.domain.me.router import router as me_router
from app.domain.workspaces.router import router as workspaces_router
from app.errors import install_error_handlers
from app.observability import RequestContextMiddleware, configure_logging


def api_router() -> APIRouter:
    api = APIRouter(prefix="/api/v1")
    api.include_router(me_router)
    api.include_router(workspaces_router)
    api.include_router(invitations_router)
    return api


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings)
    app = FastAPI(title="Gravv API", version="0.1.0", docs_url="/docs", openapi_url="/openapi.json")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-Id"],
    )
    app.add_middleware(RequestContextMiddleware)
    install_error_handlers(app)
    app.include_router(health_router)
    app.include_router(api_router())
    return app


app = create_app()
