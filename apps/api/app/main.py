from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.domain.ai_credentials.router import router as ai_credentials_router
from app.domain.analytics.router import router as analytics_router
from app.domain.captures.router import router as captures_router
from app.domain.companies.router import router as companies_router
from app.domain.contacts.router import router as contacts_router
from app.domain.exports.router import router as exports_router
from app.domain.facts.router import router as facts_router
from app.domain.health.router import router as health_router
from app.domain.insights.router import router as insights_router
from app.domain.interactions.router import router as interactions_router
from app.domain.invitations.router import router as invitations_router
from app.domain.jobs.router import router as jobs_router
from app.domain.me.router import router as me_router
from app.domain.network.router import router as network_router
from app.domain.opportunities.router import router as opportunities_router
from app.domain.search.router import router as search_router
from app.domain.tasks.router import router as tasks_router
from app.domain.workspaces.router import router as workspaces_router
from app.errors import install_error_handlers
from app.observability import RequestContextMiddleware, configure_logging
from app.ratelimit import RateLimitMiddleware


def api_router() -> APIRouter:
    api = APIRouter(prefix="/api/v1")
    api.include_router(me_router)
    api.include_router(workspaces_router)
    api.include_router(invitations_router)
    api.include_router(companies_router)
    api.include_router(contacts_router)
    api.include_router(facts_router)
    api.include_router(interactions_router)
    api.include_router(search_router)
    api.include_router(captures_router)
    api.include_router(jobs_router)
    api.include_router(insights_router)
    api.include_router(analytics_router)
    api.include_router(tasks_router)
    api.include_router(opportunities_router)
    api.include_router(network_router)
    api.include_router(exports_router)
    api.include_router(ai_credentials_router)
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
    app.add_middleware(RateLimitMiddleware, settings=settings)
    app.add_middleware(RequestContextMiddleware)
    install_error_handlers(app)
    app.include_router(health_router)
    app.include_router(api_router())
    return app


app = create_app()
