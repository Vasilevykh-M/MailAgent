from __future__ import annotations

import io

from pypdf import PdfWriter

from tests.conftest import image_bytes


def _png_file() -> dict[str, tuple[str, bytes, str]]:
    return {"file": ("sample.png", image_bytes(), "image/png")}


def _pdf_bytes(page_count: int = 1) -> bytes:
    writer = PdfWriter()
    for _ in range(page_count):
        writer.add_blank_page(width=100, height=100)
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def test_ocr_response_is_normalized_and_reuses_model(client, app_parts) -> None:
    _, adapters, _ = app_parts
    response = client.post("/api/v1/ocr", files=_png_file(), data={"return_boxes": "true", "return_confidence": "true"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["task"] == "ocr"
    assert payload["request_id"] == response.headers["X-Request-ID"]
    assert payload["text"] == "Hello\nworld"
    assert payload["pages"][0]["lines"][0] == {
        "text": "Hello",
        "confidence": 0.99,
        "polygon": [[1, 1], [9, 1], [9, 4], [1, 4]],
    }
    second = client.post("/api/v1/ocr", files=_png_file())
    assert second.status_code == 200
    assert adapters.ocr.create_calls == 1


def test_ocr_can_omit_boxes_and_confidence(client) -> None:
    response = client.post(
        "/api/v1/ocr", files=_png_file(), data={"return_boxes": "false", "return_confidence": "false"}
    )
    line = response.json()["pages"][0]["lines"][0]
    assert line["polygon"] is None
    assert line["confidence"] is None


def test_document_response_is_normalized_and_markdown_is_opt_in(client, app_parts) -> None:
    response = client.post("/api/v1/documents/parse", files=_png_file(), data={"output_format": "json"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["task"] == "document_parsing"
    assert payload["markdown"] is None
    assert payload["pages"][0]["elements"][0]["id"] == "page-0-element-10"
    assert payload["pages"][0]["elements"][1]["html"] == "<table><tr><td>x</td></tr></table>"
    markdown = client.post("/api/v1/documents/parse", files=_png_file(), data={"output_format": "markdown"})
    assert markdown.json()["markdown"] == "# Demo document"
    assert app_parts[1].document.create_calls == 1


def test_model_and_language_errors_are_422_and_include_request_id(client) -> None:
    cases = [
        {"model": "missing"},
        {"language": "made-up"},
        {"model": "pp-ocrv6", "language": "ru"},
        {"model": "pp-structurev3"},
    ]
    for data in cases:
        response = client.post("/api/v1/ocr", files=_png_file(), data=data)
        assert response.status_code == 422
        assert response.json()["error"]["request_id"] == response.headers["X-Request-ID"]


def test_output_format_and_upload_errors(client) -> None:
    output = client.post("/api/v1/documents/parse", files=_png_file(), data={"output_format": "xml"})
    assert output.status_code == 422
    unsupported = client.post("/api/v1/ocr", files={"file": ("notes.txt", b"hello", "text/plain")})
    assert unsupported.status_code == 415
    empty = client.post("/api/v1/ocr", files={"file": ("blank.png", b"", "image/png")})
    assert empty.status_code == 422
    broken_image = client.post("/api/v1/ocr", files={"file": ("broken.png", b"\x89PNG\r\n\x1a\nbad", "image/png")})
    assert broken_image.status_code == 422
    broken_pdf = client.post("/api/v1/ocr", files={"file": ("broken.pdf", b"%PDF-not-valid", "application/pdf")})
    assert broken_pdf.status_code == 422


def test_pdf_limit_and_temporary_file_cleanup(client, app_parts) -> None:
    _, _, settings = app_parts
    too_many = client.post(
        "/api/v1/ocr",
        files={"file": ("many.pdf", _pdf_bytes(3), "application/pdf")},
    )
    assert too_many.status_code == 422
    success = client.post(
        "/api/v1/ocr",
        files={"file": ("one.pdf", _pdf_bytes(), "application/pdf")},
    )
    assert success.status_code == 200
    assert list(settings.effective_temp_dir.glob("upload-*.pdf")) == []


def test_temporary_pdf_is_deleted_after_an_inference_exception(tmp_path) -> None:
    from fastapi.testclient import TestClient

    from app.core.config import Settings
    from app.main import create_app
    from tests.conftest import FakeAdapters

    settings = Settings(paddle_model_home=tmp_path / "models", temp_dir=tmp_path / "tmp")
    with TestClient(create_app(settings=settings, adapters=FakeAdapters(fail=True))) as local_client:
        response = local_client.post(
            "/api/v1/ocr",
            files={"file": ("one.pdf", _pdf_bytes(), "application/pdf")},
        )
    assert response.status_code == 502
    assert list(settings.effective_temp_dir.glob("upload-*.pdf")) == []


def test_oversized_upload_is_rejected(tmp_path) -> None:
    from fastapi.testclient import TestClient

    from app.core.config import Settings
    from app.main import create_app
    from tests.conftest import FakeAdapters

    app = create_app(
        Settings(paddle_model_home=tmp_path / "models", max_upload_size_mb=1, max_pdf_pages=2), adapters=FakeAdapters()
    )
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/ocr", files={"file": ("big.png", b"\x89PNG\r\n\x1a\n" + b"x" * (1024 * 1024), "image/png")}
        )
    assert response.status_code == 413
