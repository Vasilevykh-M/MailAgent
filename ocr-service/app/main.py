"""FastAPI application factory and lifespan wiring."""

from __future__ import annotations

import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request

from app.api.error_handlers import register_error_handlers
from app.api.routes import capabilities, documents, health, ocr
from app.core.config import Settings, get_settings, validate_runtime_directories
from app.core.logging import configure_logging
from app.core.request_context import request_id_from_header
from app.services.capabilities import CapabilitiesRegistry
from app.services.file_processor import FileProcessor
from app.services.inference_limiter import InferenceLimiter
from app.services.model_manager import ModelManager
from app.services.paddle_adapters import AdapterFactory
from app.services.processing_service import ProcessingService

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None, adapters: AdapterFactory | None = None) -> FastAPI:
    """Create an app without importing or initializing heavyweight PaddleOCR models."""

    configured_settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        configure_logging(configured_settings.log_level)
        registry = CapabilitiesRegistry()
        registry.validate_defaults(configured_settings)
        validate_runtime_directories(configured_settings)
        models = ModelManager(configured_settings, adapters=adapters)
        app.state.settings = configured_settings
        app.state.registry = registry
        app.state.models = models
        app.state.processing_service = ProcessingService(
            configured_settings,
            registry,
            FileProcessor(configured_settings),
            models,
            InferenceLimiter(
                configured_settings.max_concurrent_inferences, configured_settings.request_timeout_seconds
            ),
        )
        yield
        await models.close()

    app = FastAPI(
        title="PaddleOCR Service",
        description=(
            "Production-oriented, lazy-loading PaddleOCR service. Models and languages are discovered via "
            "`/api/v1/capabilities`; inference runs outside the event loop."
        ),
        version="1.0.0",
        lifespan=lifespan,
    )

    @app.middleware("http")
    async def request_context(request: Request, call_next):  # type: ignore[no-untyped-def]
        request.state.request_id = request_id_from_header(request.headers.get("X-Request-ID"))
        started = time.perf_counter()
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        logger.info(
            "request_completed request_id=%s method=%s endpoint=%s status=%s duration_ms=%s",
            request.state.request_id,
            request.method,
            request.url.path,
            response.status_code,
            int((time.perf_counter() - started) * 1000),
        )
        return response

    register_error_handlers(app)
    app.include_router(health.router)
    app.include_router(capabilities.router)
    app.include_router(ocr.router)
    app.include_router(documents.router)
    return app


app = create_app()
