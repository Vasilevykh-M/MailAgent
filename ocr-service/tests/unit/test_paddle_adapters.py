from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType

import pytest

from app.core.config import Settings
from app.services.paddle_adapters import PaddleDocumentParserAdapter, PaddleOcrAdapter


class _FakePipeline:
    def __init__(self, **kwargs: object) -> None:
        self.kwargs = kwargs


@pytest.fixture
def fake_paddleocr(monkeypatch: pytest.MonkeyPatch) -> None:
    module = ModuleType("paddleocr")
    module.PaddleOCR = _FakePipeline
    module.PPStructureV3 = _FakePipeline
    monkeypatch.setitem(sys.modules, "paddleocr", module)


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        paddle_model_home=tmp_path / "models",
        temp_dir=tmp_path / "tmp",
        paddle_enable_mkldnn=False,
    )


def test_ocr_adapter_explicitly_disables_mkldnn(fake_paddleocr: None, tmp_path: Path) -> None:
    pipeline = PaddleOcrAdapter().create("pp-ocrv6", "ru", _settings(tmp_path))

    assert pipeline.kwargs["enable_mkldnn"] is False
    assert pipeline.kwargs["device"] == "cpu"
    assert pipeline.kwargs["ocr_version"] == "PP-OCRv6"


def test_document_adapter_explicitly_disables_mkldnn(fake_paddleocr: None, tmp_path: Path) -> None:
    pipeline = PaddleDocumentParserAdapter().create("pp-structurev3", "ru", _settings(tmp_path))

    assert pipeline.kwargs["enable_mkldnn"] is False
    assert pipeline.kwargs["device"] == "cpu"
    assert pipeline.kwargs["ocr_version"] == "PP-OCRv5"
