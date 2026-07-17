from pathlib import Path

import pytest

from yandex_mail.config import DEFAULT_REDIRECT_URI, YandexMailConfig
from yandex_mail.exceptions import ConfigurationError


def test_loads_env_and_resolves_token_file(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text("\n".join((
        "YANDEX_CLIENT_ID=id", "YANDEX_CLIENT_SECRET=secret", "YANDEX_EMAIL=user@yandex.ru",
        "YANDEX_TOKEN_FILE=tokens.json",
    )), encoding="utf-8")
    config = YandexMailConfig.from_env(env)
    config.validate()
    assert config.redirect_uri == DEFAULT_REDIRECT_URI
    assert config.token_file == tmp_path / "tokens.json"


def test_invalid_required_settings_raise_clear_error() -> None:
    with pytest.raises(ConfigurationError, match="YANDEX_CLIENT_ID"):
        YandexMailConfig().validate()
