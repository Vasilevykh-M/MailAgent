from __future__ import annotations

import hashlib

import httpx
import pytest

from mail_agent.clients.results_api import ResultsAPIClient
from mail_agent.config import ResultsAPISettings
from mail_agent.exceptions import ResultsAPIPermanentError


def _payload(digest: str) -> dict[str, object]:
    return {
        "record_id": "a" * 64,
        "processing_generation": 2,
        "files": [{"part_name": "attachment_0", "safe_filename": "file.txt", "sha256": digest}],
    }


def test_results_api_retries_with_stable_idempotency_key_and_streamed_files(tmp_path) -> None:
    attachment = tmp_path / "attachment"
    attachment.write_bytes(b"attachment bytes")
    raw = tmp_path / "raw.eml"
    raw.write_bytes(b"From: sender@example.test\r\n\r\nbody")
    digest = hashlib.sha256(attachment.read_bytes()).hexdigest()
    client = ResultsAPIClient(ResultsAPISettings(base_url="http://results.test", api_key="writer", max_retries=1))
    attempts: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(request)
        if len(attempts) == 1:
            return httpx.Response(500)
        return httpx.Response(
            200,
            json={
                "record_id": "a" * 64,
                "status": "committed",
                "processing_generation": 2,
                "attachment_count": 1,
                "storage_verified": True,
                "committed_at": "2026-07-17T10:04:00Z",
            },
        )

    client._client = httpx.Client(transport=httpx.MockTransport(handler), base_url="http://results.test")
    client._sleep = lambda _attempt: None  # type: ignore[method-assign]
    try:
        committed = client.persist(_payload(digest), raw_email_path=raw, attachment_paths={digest: str(attachment)})
    finally:
        client.close()

    assert committed.status == "committed"
    assert [request.headers["Idempotency-Key"] for request in attempts] == ["a" * 64, "a" * 64]
    assert all(request.headers["X-API-Key"] == "writer" for request in attempts)
    assert b"attachment bytes" in attempts[-1].content
    assert b"original.eml" in attempts[-1].content


def test_results_api_treats_4xx_as_permanent(tmp_path) -> None:
    raw = tmp_path / "raw.eml"
    raw.write_bytes(b"raw")
    client = ResultsAPIClient(ResultsAPISettings(base_url="http://results.test", api_key="writer"))
    client._client = httpx.Client(
        transport=httpx.MockTransport(lambda _request: httpx.Response(400)), base_url="http://results.test"
    )
    try:
        with pytest.raises(ResultsAPIPermanentError):
            client.persist(
                {"record_id": "a" * 64, "processing_generation": 0, "files": []},
                raw_email_path=raw,
                attachment_paths={},
            )
    finally:
        client.close()
