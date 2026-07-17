"""Strict, non-persistent validation and materialization of uploaded files."""

from __future__ import annotations

import asyncio
import io
import os
import tempfile
import warnings
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from fastapi import UploadFile
from PIL import Image, UnidentifiedImageError
from pypdf import PdfReader

from app.core.config import Settings
from app.core.exceptions import (
    CorruptedImageError,
    CorruptedPdfError,
    EmptyFileError,
    OversizedFileError,
    PdfPageLimitError,
    UnsupportedFileError,
)
from app.services.capabilities import SUPPORTED_EXTENSIONS, SUPPORTED_MIME_TYPES

_CHUNK_SIZE = 64 * 1024
_MAX_IMAGE_PIXELS = 100_000_000
_IMAGE_SIGNATURES = {
    ".png": b"\x89PNG\r\n\x1a\n",
    ".jpg": b"\xff\xd8\xff",
    ".jpeg": b"\xff\xd8\xff",
}


@dataclass(frozen=True)
class ProcessedFile:
    """Validated content kept only for the lifetime of the request."""

    kind: str
    data: bytes
    page_count: int
    dimensions: tuple[tuple[int | None, int | None], ...]
    extension: str


class FileProcessor:
    """Applies length, MIME, signature and parser validation before inference."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def prepare(self, upload: UploadFile) -> ProcessedFile:
        extension = Path(upload.filename or "").suffix.lower()
        if extension not in SUPPORTED_EXTENSIONS:
            raise UnsupportedFileError(
                "Only JPEG, PNG, and PDF uploads are supported",
                details={"supported_extensions": list(SUPPORTED_EXTENSIONS)},
            )
        if upload.content_type not in SUPPORTED_MIME_TYPES:
            raise UnsupportedFileError(
                "The upload MIME type is not supported",
                details={"supported_mime_types": list(SUPPORTED_MIME_TYPES)},
            )
        data = await self._read_limited(upload)
        if not data:
            raise EmptyFileError("The uploaded file is empty")
        if data.startswith(b"%PDF-"):
            if extension != ".pdf" or upload.content_type != "application/pdf":
                raise UnsupportedFileError("File extension or MIME type does not match the PDF content")
            return await asyncio.to_thread(self._validate_pdf, data)
        if extension == ".pdf":
            raise CorruptedPdfError("The PDF file is corrupted or invalid")
        if not self._matches_image_signature(extension, data):
            raise CorruptedImageError("The image content does not match its declared format")
        return await asyncio.to_thread(self._validate_image, data, extension)

    async def _read_limited(self, upload: UploadFile) -> bytes:
        parts: list[bytes] = []
        size = 0
        try:
            while chunk := await upload.read(_CHUNK_SIZE):
                size += len(chunk)
                if size > self._settings.max_upload_size_bytes:
                    raise OversizedFileError(
                        f"The upload exceeds the {self._settings.max_upload_size_mb} MB limit",
                        details={"max_upload_size_mb": self._settings.max_upload_size_mb},
                    )
                parts.append(chunk)
        finally:
            await upload.close()
        return b"".join(parts)

    @staticmethod
    def _matches_image_signature(extension: str, data: bytes) -> bool:
        signature = _IMAGE_SIGNATURES[extension]
        return data.startswith(signature)

    def _validate_image(self, data: bytes, extension: str) -> ProcessedFile:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(io.BytesIO(data)) as image:
                    image.verify()
                with Image.open(io.BytesIO(data)) as image:
                    image.load()
                    if image.width * image.height > _MAX_IMAGE_PIXELS:
                        raise CorruptedImageError("The image dimensions exceed the safety limit")
                    dimensions = ((image.width, image.height),)
        except CorruptedImageError:
            raise
        except (
            Image.DecompressionBombError,
            Image.DecompressionBombWarning,
            UnidentifiedImageError,
            OSError,
            ValueError,
        ) as exc:
            raise CorruptedImageError("The image file is corrupted or unreadable") from exc
        return ProcessedFile("image", data, 1, dimensions, extension)

    def _validate_pdf(self, data: bytes) -> ProcessedFile:
        try:
            reader = PdfReader(io.BytesIO(data), strict=True)
            page_count = len(reader.pages)
            if page_count == 0:
                raise CorruptedPdfError("The PDF contains no pages")
            if page_count > self._settings.max_pdf_pages:
                raise PdfPageLimitError(
                    f"The PDF exceeds the {self._settings.max_pdf_pages}-page limit",
                    details={"max_pdf_pages": self._settings.max_pdf_pages, "page_count": page_count},
                )
            dimensions = tuple(
                (int(float(page.mediabox.width)), int(float(page.mediabox.height))) for page in reader.pages
            )
        except (CorruptedPdfError, PdfPageLimitError):
            raise
        except Exception as exc:
            raise CorruptedPdfError("The PDF file is corrupted or unreadable") from exc
        return ProcessedFile("pdf", data, page_count, dimensions, ".pdf")

    @asynccontextmanager
    async def inference_input(self, processed: ProcessedFile):
        """Yield a NumPy image or a private PDF path and always remove the latter."""

        if processed.kind == "image":
            image = await asyncio.to_thread(self._to_array, processed.data)
            yield image
            return
        path = await asyncio.to_thread(self._write_private_pdf, processed.data)
        try:
            yield str(path)
        finally:
            await asyncio.to_thread(path.unlink, missing_ok=True)

    @staticmethod
    def _to_array(data: bytes) -> np.ndarray:
        with Image.open(io.BytesIO(data)) as image:
            return np.asarray(image.convert("RGB"))

    def _write_private_pdf(self, data: bytes) -> Path:
        directory = self._settings.effective_temp_dir
        directory.mkdir(parents=True, exist_ok=True)
        file_descriptor, raw_path = tempfile.mkstemp(prefix="upload-", suffix=".pdf", dir=directory)
        try:
            with os.fdopen(file_descriptor, "wb") as temporary_file:
                temporary_file.write(data)
            return Path(raw_path)
        except BaseException:
            Path(raw_path).unlink(missing_ok=True)
            raise
