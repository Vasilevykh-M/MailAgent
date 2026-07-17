"""Optional real-model smoke test; never run by default."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.mark.integration
def test_real_paddleocr_smoke() -> None:
    image_path = os.getenv("PADDLE_SMOKE_IMAGE")
    if os.getenv("RUN_PADDLE_SMOKE") != "1" or not image_path:
        pytest.skip("set RUN_PADDLE_SMOKE=1 and PADDLE_SMOKE_IMAGE=/path/to/image.png to run real PaddleOCR")
    path = Path(image_path)
    if not path.is_file():
        pytest.skip("PADDLE_SMOKE_IMAGE does not point to an available image")
    with TestClient(create_app()) as client:
        with path.open("rb") as image:
            response = client.post("/api/v1/ocr", files={"file": (path.name, image, "image/png")})
    assert response.status_code == 200, response.text
