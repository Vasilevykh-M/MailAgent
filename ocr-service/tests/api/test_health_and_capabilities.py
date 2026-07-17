from __future__ import annotations


def test_live_is_lightweight_and_returns_request_id(client, app_parts) -> None:
    _, adapters, _ = app_parts
    response = client.get("/health/live", headers={"X-Request-ID": "safe-test-id"})
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["X-Request-ID"] == "safe-test-id"
    assert adapters.ocr.create_calls == 0
    assert adapters.document.create_calls == 0


def test_ready_does_not_eagerly_load_models(client, app_parts) -> None:
    _, adapters, _ = app_parts
    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json()["loaded_models"] == 0
    assert adapters.ocr.create_calls == 0
    assert adapters.document.create_calls == 0


def test_capabilities_are_valid_and_openapi_is_lightweight(client, app_parts) -> None:
    _, adapters, _ = app_parts
    response = client.get("/api/v1/capabilities")
    payload = response.json()
    assert "ocr" in payload["tasks"]
    assert "document_parsing" in payload["tasks"]
    all_ids = [model["id"] for task in payload["tasks"].values() for model in task["models"]]
    assert len(all_ids) == len(set(all_ids))
    for task in payload["tasks"].values():
        default = next(model for model in task["models"] if model["id"] == task["default_model"])
        assert task["default_language"] in default["languages"]
    schema = client.get("/openapi.json")
    assert schema.status_code == 200
    assert {"/health/live", "/health/ready", "/api/v1/capabilities", "/api/v1/ocr", "/api/v1/documents/parse"} <= set(
        schema.json()["paths"]
    )
    assert adapters.ocr.create_calls == 0
