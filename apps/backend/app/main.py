"""FastAPI application factory and lifespan wiring."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware

from app.ai.provider import close_ai_provider
from app.api.v1.router import api_router
from app.core.config import settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging, get_logger
from app.db.session import dispose_engine
from app.middleware.request_context import RequestContextMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.services.realtime import event_bus

log = get_logger("main")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    log.info("app_startup", env=settings.app_env, dry_run=settings.blockchain_dry_run)
    await _ensure_badge_catalog()
    yield
    await close_ai_provider()
    await event_bus.close()
    await dispose_engine()
    log.info("app_shutdown")


async def _ensure_badge_catalog() -> None:
    """Idempotently seed the badge catalog (tolerates an unavailable DB)."""
    try:
        from app.db.session import session_scope
        from app.services.social_service import BadgeService

        async with session_scope() as session:
            await BadgeService(session).ensure_catalog()
    except Exception as exc:  # noqa: BLE001
        log.warning("badge_catalog_seed_skipped", error=str(exc))


def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(
        title="QLoot API",
        description="Gamified learning on Web3 + AI",
        version="0.1.0",
        openapi_url=f"{settings.api_v1_prefix}/openapi.json",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # Middleware (order matters: outermost first).
    app.add_middleware(GZipMiddleware, minimum_size=1024)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )

    register_exception_handlers(app)
    app.include_router(api_router, prefix=settings.api_v1_prefix)

    @app.get("/", include_in_schema=False)
    async def root() -> dict[str, str]:
        return {"name": settings.app_name, "docs": "/docs", "api": settings.api_v1_prefix}

    return app


app = create_app()
