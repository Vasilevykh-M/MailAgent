"""Centralized safe error serialization."""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.exceptions import ServiceError
from app.core.request_context import get_request_id
from app.schemas.common import ErrorBody, ErrorResponse

logger = logging.getLogger(__name__)


def _response(request: Request, status_code: int, code: str, message: str, details: dict | None = None) -> JSONResponse:
    request_id = get_request_id(request)
    body = ErrorResponse(error=ErrorBody(code=code, message=message, details=details or {}, request_id=request_id))
    return JSONResponse(status_code=status_code, content=body.model_dump(), headers={"X-Request-ID": request_id})


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ServiceError)
    async def service_error_handler(request: Request, exc: ServiceError) -> JSONResponse:
        logger.warning("service_error request_id=%s error_type=%s", get_request_id(request), exc.code)
        return _response(request, exc.status_code, exc.code, exc.message, exc.details)

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, _: RequestValidationError) -> JSONResponse:
        return _response(request, 422, "validation_error", "The request parameters are invalid")

    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        message = (
            "The requested resource was not found" if exc.status_code == 404 else "The request could not be processed"
        )
        return _response(request, exc.status_code, "http_error", message)

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("internal_error request_id=%s error_type=%s", get_request_id(request), type(exc).__name__)
        return _response(request, 500, "internal_error", "An unexpected internal error occurred")
