from __future__ import annotations

import pytest
from pydantic import ValidationError

from mail_agent.config import DashboardSettings, LimitsSettings, LLMSettings


def test_llm_default_targets_the_dedicated_llm_host() -> None:
    assert LLMSettings().base_url == "http://192.168.88.251:8001/v1"


def test_message_body_chunk_default_is_3000_characters() -> None:
    assert LimitsSettings().message_body_chunk_size == 3_000


@pytest.mark.parametrize("host", ["localhost", "127.0.0.1", "::1", "192.168.88.32", "10.10.0.12"])
def test_dashboard_allows_loopback_and_private_addresses(host: str) -> None:
    assert DashboardSettings(host=host).host == host


@pytest.mark.parametrize("host", ["0.0.0.0", "8.8.8.8", "dashboard.example.test"])
def test_dashboard_rejects_unspecified_public_and_hostname_addresses(host: str) -> None:
    with pytest.raises(ValidationError):
        DashboardSettings(host=host)
