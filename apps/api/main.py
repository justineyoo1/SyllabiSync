from __future__ import annotations

import logging

from fastapi import FastAPI

from apps.api.routers import health, uploads, qa, calendar, documents
from packages.common.config import get_settings
from packages.common.logging import setup_json_logging


def create_app() -> FastAPI:
    settings = get_settings()
    setup_json_logging(settings.log_level)
    app = FastAPI(title=settings.app_name)

    # Routers
    app.include_router(health.router)
    app.include_router(uploads.router)
    app.include_router(qa.router)
    app.include_router(calendar.router)
    app.include_router(documents.router)

    logging.getLogger(__name__).info("api_started", extra={"environment": settings.environment})
    return app


app = create_app()


