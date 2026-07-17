"""Dependency helpers that expose shared lifespan components to routers."""

from __future__ import annotations

from fastapi import Request

from app.services.processing_service import ProcessingService


def get_processing_service(request: Request) -> ProcessingService:
    return request.app.state.processing_service
