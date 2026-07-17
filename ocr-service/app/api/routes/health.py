"""Liveness and lightweight readiness endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.core.config import validate_runtime_directories
from app.schemas.common import LiveResponse, ReadyResponse

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live", response_model=LiveResponse, summary="Liveness probe")
async def live() -> LiveResponse:
    """Confirm the process is running without loading or downloading any model."""

    return LiveResponse()


@router.get("/ready", response_model=ReadyResponse, summary="Readiness probe")
async def ready(request: Request) -> ReadyResponse:
    """Check settings, writable directories and registry without eager model loading."""

    settings = request.app.state.settings
    request.app.state.registry.validate_defaults(settings)
    validate_runtime_directories(settings)
    return ReadyResponse(device=settings.paddle_device, loaded_models=request.app.state.models.loaded_model_count)
