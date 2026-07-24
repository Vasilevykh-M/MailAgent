from __future__ import annotations

import json
import logging

import httpx
import pytest
from pydantic import BaseModel, Field

from mail_agent.clients.llm import LLMClient
from mail_agent.config import LLMSettings
from mail_agent.exceptions import PermanentError


class Result(BaseModel):
    summary_ru: str
    confidence: float = Field(ge=0, le=1)


def _client(handler: httpx.MockTransport) -> LLMClient:
    client = LLMClient(LLMSettings(base_url="http://llm.test/v1", model="qwen3.5-vlm", max_retries=0))
    client.close()
    client._client = httpx.Client(transport=handler, base_url="http://llm.test/v1/")
    return client


def test_structured_sends_pydantic_json_schema() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["payload"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"summary_ru":"Готово","confidence":0.9}'}}]},
        )

    client = _client(httpx.MockTransport(handler))
    try:
        result = client.structured("Return JSON.", "Private email body", Result)
    finally:
        client.close()

    payload = captured["payload"]
    assert isinstance(payload, dict)
    messages = payload["messages"]
    assert isinstance(messages, list)
    system = messages[0]["content"]
    assert isinstance(system, str)
    assert "JSON Schema" in system
    assert '"summary_ru"' in system
    assert "Trusted runtime context" in system
    assert "Current processing time:" in system
    assert result.summary_ru == "Готово"


def test_structured_logs_only_invalid_response_type(caplog) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{"message": {"content": "private model response"}}]})

    client = _client(httpx.MockTransport(handler))
    caplog.set_level(logging.ERROR, logger="mail_agent.clients.llm")
    try:
        with pytest.raises(PermanentError):
            client.structured("Return JSON.", "Private email body", Result)
    finally:
        client.close()

    record = next(record for record in caplog.records if record.getMessage() == "llm_structured_response_invalid")
    assert record.error_type == "PermanentError"
    assert record.error_code == "invalid_json"
    assert "private model response" not in record.getMessage()
    assert not hasattr(record, "response_content")


def test_structured_bounds_large_user_input_and_does_not_retry_bad_request() -> None:
    requests = 0
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        captured["payload"] = json.loads(request.content)
        return httpx.Response(400, json={"error": {"message": "context too long"}})

    client = _client(httpx.MockTransport(handler))
    client.settings.max_text_chars_per_request = 40
    client.settings.max_retries = 3
    try:
        with pytest.raises(PermanentError, match="HTTP 400"):
            client.structured("Return JSON.", "a" * 100, Result)
    finally:
        client.close()

    payload = captured["payload"]
    assert isinstance(payload, dict)
    messages = payload["messages"]
    assert isinstance(messages, list)
    assert len(messages[1]["content"]) <= 40
    assert requests == 1


def test_structured_retries_invalid_model_json_and_uses_json_mode() -> None:
    requests = 0
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        captured["payload"] = json.loads(request.content)
        content = (
            "<think>not part of the response</think>"
            if requests == 1
            else 'prefix {"summary_ru":"Готово","confidence":0.9}'
        )
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})

    client = _client(httpx.MockTransport(handler))
    try:
        result = client.structured("Return JSON.", "Private email body", Result)
    finally:
        client.close()

    assert requests == 2
    assert result.summary_ru == "Готово"
    payload = captured["payload"]
    assert isinstance(payload, dict)
    assert payload["response_format"] == {
        "type": "json_schema",
        "json_schema": {"name": "Result", "schema": Result.model_json_schema(), "strict": True},
    }


def test_structured_ignores_reasoning_wrapper_before_valid_json() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {
                            "content": (
                                '<think>{"summary_ru":"черновик","confidence":"не число"}</think>\n'
                                '```json\n{"summary_ru":"Готово","confidence":0.9}\n```'
                            )
                        },
                    }
                ]
            },
        )

    client = _client(httpx.MockTransport(handler))
    try:
        result = client.structured("Return JSON.", "Private email body", Result)
    finally:
        client.close()

    assert result.summary_ru == "Готово"


def test_structured_message_budget_stops_request_amplification() -> None:
    requests = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"summary_ru":"Готово","confidence":0.9}'}}]},
        )

    client = _client(httpx.MockTransport(handler))
    try:
        with client.message_budget(1):
            client.structured("Return JSON.", "first", Result)
            with pytest.raises(PermanentError, match="лимит LLM-запросов"):
                client.structured("Return JSON.", "second", Result)
    finally:
        client.close()

    assert requests == 1
