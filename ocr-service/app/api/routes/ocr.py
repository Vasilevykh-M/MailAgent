"""General OCR API endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile

from app.api.dependencies import get_processing_service
from app.core.request_context import get_request_id
from app.schemas.common import ErrorResponse
from app.schemas.ocr import OcrResponse
from app.services.processing_service import ProcessingService

router = APIRouter(prefix="/api/v1", tags=["ocr"])


@router.post(
    "/ocr",
    response_model=OcrResponse,
    responses={
        413: {"model": ErrorResponse, "description": "Upload exceeds its configured size limit"},
        415: {"model": ErrorResponse, "description": "Unsupported MIME type or file format"},
        422: {"model": ErrorResponse, "description": "Invalid model, language, PDF or request parameter"},
        503: {"model": ErrorResponse, "description": "Model loading failed"},
    },
    summary="Recognize text in a JPEG, PNG or PDF",
)
async def ocr(
    request: Request,
    file: UploadFile = File(description="JPEG, PNG, or PDF; size and page count limits are exposed by /capabilities"),
    model: str | None = Form(default=None, description="OCR model ID from /api/v1/capabilities"),
    language: str | None = Form(default=None, description="Language code compatible with the selected model"),
    return_boxes: bool = Form(default=True, description="Include normalized line polygons when true"),
    return_confidence: bool = Form(default=True, description="Include recognition confidence scores when true"),
    service: ProcessingService = Depends(get_processing_service),
) -> OcrResponse:
    """Run lazy, cached PaddleOCR inference in a worker thread."""

    return await service.ocr(
        file,
        request_id=get_request_id(request),
        model=model,
        language=language,
        return_boxes=return_boxes,
        return_confidence=return_confidence,
    )
