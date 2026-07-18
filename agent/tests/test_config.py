from __future__ import annotations

import pytest
from pydantic import ValidationError

from mail_agent.config import DashboardSettings


@pytest.mark.parametrize("host", ["localhost", "127.0.0.1", "::1", "192.168.88.32", "10.10.0.12"])
def test_dashboard_allows_loopback_and_private_addresses(host: str) -> None:
    assert DashboardSettings(host=host).host == host


@pytest.mark.parametrize("host", ["0.0.0.0", "8.8.8.8", "dashboard.example.test"])
def test_dashboard_rejects_unspecified_public_and_hostname_addresses(host: str) -> None:
    with pytest.raises(ValidationError):
        DashboardSettings(host=host)
