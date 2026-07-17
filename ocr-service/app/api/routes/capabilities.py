"""Capability discovery endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.schemas.capabilities import CapabilitiesResponse

router = APIRouter(prefix="/api/v1", tags=["capabilities"])


@router.get(
    "/capabilities",
    response_model=CapabilitiesResponse,
    summary="List available tasks, models, languages and output formats",
)
async def capabilities(request: Request) -> CapabilitiesResponse:
    """Return the single registry used for validation and model construction."""

    return request.app.state.registry.response(request.app.state.settings)
