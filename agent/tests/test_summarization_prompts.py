from __future__ import annotations

from mail_agent.summarization.prompts import (
    ATTACHMENT_CHUNK_SYSTEM,
    ATTACHMENT_REDUCE_SYSTEM,
    FORWARDED_MESSAGE_CHUNK_SYSTEM,
    FORWARDED_MESSAGE_REDUCE_SYSTEM,
    SPREADSHEET_CHUNK_SYSTEM,
    SPREADSHEET_REDUCE_SYSTEM,
    SUMMARY_SYSTEM,
)


def test_summary_prompts_distinguish_runtime_time_from_email_claims() -> None:
    for prompt in (
        SUMMARY_SYSTEM,
        ATTACHMENT_CHUNK_SYSTEM,
        ATTACHMENT_REDUCE_SYSTEM,
        FORWARDED_MESSAGE_CHUNK_SYSTEM,
        FORWARDED_MESSAGE_REDUCE_SYSTEM,
        SPREADSHEET_CHUNK_SYSTEM,
        SPREADSHEET_REDUCE_SYSTEM,
    ):
        assert "current processing time" in prompt
        assert "relative dates" in prompt
        assert "changing world facts" in prompt

    assert "message date" in SUMMARY_SYSTEM
    assert "ISO-8601" in SUMMARY_SYSTEM
