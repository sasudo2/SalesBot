import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.chat import router as chat_router
from app.api.errors import exception_handlers
from app.api.health import router as health_router
from app.api.middleware import _RequestIdFilter, request_id_middleware
from app.core.config import load_settings
from app.db.init import init_db
from app.services.jobs import run_expiry_once

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    settings = load_settings()
    logging.basicConfig(
        level=settings.log_level.upper(),
        format="%(levelname)s %(name)s request_id=%(request_id)s %(message)s",
    )
    for handler in logging.getLogger().handlers:
        if not any(isinstance(f, _RequestIdFilter) for f in handler.filters):
            handler.addFilter(_RequestIdFilter())

    async def _expiry_job() -> None:
        while True:
            await asyncio.sleep(settings.expire_job_interval_s)
            try:
                await asyncio.to_thread(run_expiry_once)
            except Exception:
                logger.exception("Cart expiry job failed")

    @asynccontextmanager
    async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
        if settings.app_env != "prod":
            init_db()
        job = asyncio.create_task(_expiry_job()) if settings.expire_job_interval_s > 0 else None
        try:
            yield
        finally:
            if job:
                job.cancel()
                with suppress(asyncio.CancelledError):
                    await job

    application = FastAPI(lifespan=_lifespan)
    application.middleware("http")(request_id_middleware)
    exception_handlers(application)
    application.include_router(chat_router)
    application.include_router(health_router)
    if settings.cors_origins:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_methods=["GET", "POST"],
            allow_headers=["X-API-Key", "X-Request-ID", "Content-Type"],
        )
    return application


app = create_app()
