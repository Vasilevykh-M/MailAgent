from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.core.config import Settings
from app.core.exceptions import InferenceError
from app.main import create_app
from app.services.capabilities import DOCUMENT_TASK, OCR_TASK


@dataclass
class FakePipeline:
    task: str
    fail: bool = False


class FakeDocumentResult:
    def __init__(self) -> None:
        self.json = {
            "res": {
                "page_index": 0,
                "width": 20,
                "height": 10,
                "parsing_res_list": [
                    {
                        "block_label": "doc_title",
                        "block_content": "Demo document",
                        "block_bbox": [1, 2, 19, 5],
                        "block_id": 10,
                        "block_order": 0,
                    },
                    {
                        "block_label": "table",
                        "block_content": None,
                        "block_bbox": [1, 5, 19, 9],
                        "block_id": 11,
                        "block_order": 1,
                    },
                ],
                "table_res_list": [{"table_region_id": 11, "pred_html": "<table><tr><td>x</td></tr></table>"}],
                "formula_res_list": [],
            }
        }
        self.markdown = {"markdown_texts": "# Demo document"}


class FakeAdapter:
    def __init__(self, task: str, *, fail: bool = False) -> None:
        self.task = task
        self.fail = fail
        self.create_calls = 0
        self.release_calls = 0

    def create(self, model: str, language: str, settings: Settings) -> FakePipeline:
        self.create_calls += 1
        return FakePipeline(self.task, self.fail)

    def predict(self, pipeline: FakePipeline, input_value: Any, **parameters: Any) -> list[Any]:
        if pipeline.fail:
            raise InferenceError("fake inference failure")
        if pipeline.task == OCR_TASK:
            return [
                {
                    "res": {
                        "page_index": 0,
                        "rec_texts": ["Hello", "world"],
                        "rec_scores": [0.99, 0.88],
                        "rec_polys": [[[1, 1], [9, 1], [9, 4], [1, 4]], [[1, 5], [10, 5], [10, 9], [1, 9]]],
                    }
                }
            ]
        return [FakeDocumentResult()]

    def release(self, pipeline: FakePipeline) -> None:
        self.release_calls += 1


class FakeAdapters:
    def __init__(self, *, fail: bool = False) -> None:
        self.ocr = FakeAdapter(OCR_TASK, fail=fail)
        self.document = FakeAdapter(DOCUMENT_TASK, fail=fail)

    def for_task(self, task: str) -> FakeAdapter:
        return self.ocr if task == OCR_TASK else self.document


def image_bytes() -> bytes:
    image = Image.new("RGB", (20, 10), "white")
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


@pytest.fixture
def app_parts(tmp_path: Path):
    adapters = FakeAdapters()
    settings = Settings(
        paddle_model_home=tmp_path / "models",
        temp_dir=tmp_path / "tmp",
        model_cache_size=2,
        max_upload_size_mb=1,
        max_pdf_pages=2,
        request_timeout_seconds=5,
    )
    return create_app(settings=settings, adapters=adapters), adapters, settings


@pytest.fixture
def client(app_parts):
    app, _, _ = app_parts
    with TestClient(app) as test_client:
        yield test_client
