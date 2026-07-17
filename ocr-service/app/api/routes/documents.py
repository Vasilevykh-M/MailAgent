"""PP-StructureV3 document parsing API endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile

from app.api.dependencies import get_processing_service
from app.core.request_context import get_request_id
from app.schemas.common import ErrorResponse
from app.schemas.documents import DocumentParseResponse
from app.services.processing_service import ProcessingService

router = APIRouter(prefix="/api/v1/documents", tags=["document parsing"])


@router.post(
    "/parse",
    response_model=DocumentParseResponse,
    responses={
        413: {"model": ErrorResponse, "description": "Upload exceeds its configured size limit"},
        415: {"model": ErrorResponse, "description": "Unsupported MIME type or file format"},
        422: {
            "model": ErrorResponse,
            "description": "Invalid model, language, PDF, output format or request parameter",
        },
        503: {"model": ErrorResponse, "description": "Model loading failed"},
    },
    summary="Parse document structure from a JPEG, PNG or PDF",
)
async def parse_document(
    request: Request,
    file: UploadFile = File(description="JPEG, PNG, or PDF; documents are deleted when the request finishes"),
    model: str | None = Form(default=None, description="Document parser model ID from /api/v1/capabilities"),
    language: str | None = Form(default=None, description="Language code compatible with the selected parser"),
    output_format: str = Form(
        default="json", description="json, markdown, or both; Markdown is generated only when requested"
    ),
    service: ProcessingService = Depends(get_processing_service),
) -> DocumentParseResponse:
    """Run cached PP-StructureV3 and return normalized structural elements."""

    return await service.document_parse(
        file,
        request_id=get_request_id(request),
        model=model,
        language=language,
        output_format=output_format,
    )
