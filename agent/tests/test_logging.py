from __future__ import annotations

import json
import logging

from mail_agent.logging import JsonFormatter, log_event


def test_json_formatter_keeps_only_whitelisted_technical_fields() -> None:
    logger = logging.getLogger("test.safe-log")
    record = logger.makeRecord(
        logger.name,
        logging.INFO,
        __file__,
        1,
        "stage_completed",
        (),
        None,
        extra={
            "component": "graph",
            "record_id": "record-1",
            "duration_ms": 12,
            "message_body": "private mail content",
            "authorization": "secret",
        },
    )

    payload = json.loads(JsonFormatter().format(record))

    assert payload["event"] == "stage_completed"
    assert payload["component"] == "graph"
    assert payload["record_id"] == "record-1"
    assert payload["duration_ms"] == 12
    assert "message_body" not in payload
    assert "authorization" not in payload


def test_log_event_rejects_non_whitelisted_fields() -> None:
    logger = logging.getLogger("test.safe-log")

    try:
        log_event(logger, "unsafe", message_body="private")
    except ValueError as exc:
        assert "Небезопасные поля" in str(exc)
    else:
        raise AssertionError("Небезопасное поле не было отклонено")
