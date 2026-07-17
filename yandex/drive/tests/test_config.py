from __future__ import annotations

from pathlib import Path

import pytest

from yandex_drive import ConfigurationError, YandexDriveConfig


def test_env_loading_priority_and_relative_token_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env = tmp_path / ".env"
    env.write_text(
        "\n".join((
            "YANDEX_DRIVE_CLIENT_ID=file-drive-id",
            "YANDEX_CLIENT_ID=file-generic-id",
            "YANDEX_DRIVE_CLIENT_SECRET=file-drive-secret",
            "YANDEX_CLIENT_SECRET=file-generic-secret",
            "YANDEX_DRIVE_TOKEN_FILE=state/token.json",
        )),
        encoding="utf-8",
    )
    monkeypatch.setenv("YANDEX_CLIENT_ID", "process-generic-id")
    monkeypatch.setenv("YANDEX_DRIVE_CLIENT_SECRET", "process-drive-secret")
    config = YandexDriveConfig.from_env(env)
    assert config.client_id == "process-generic-id"
    assert config.client_secret == "process-drive-secret"
    assert config.token_file == tmp_path / "state/token.json"
    config.validate()


def test_drive_specific_process_value_wins_and_generic_fallback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("YANDEX_DRIVE_CLIENT_ID", "drive-id")
    monkeypatch.setenv("YANDEX_CLIENT_ID", "generic-id")
    monkeypatch.setenv("YANDEX_CLIENT_SECRET", "generic-secret")
    config = YandexDriveConfig.from_env(tmp_path / "missing.env")
    assert config.client_id == "drive-id"
    assert config.client_secret == "generic-secret"


@pytest.mark.parametrize(
    ("scope", "valid"),
    [
        ("cloud_api:disk.read,cloud_api:disk.write", True),
        (" cloud_api:disk.read   cloud_api:disk.write ", True),
        ("cloud_api:disk.read", False),
        ("cloud_api:disk.write", False),
    ],
)
def test_scope_normalization_and_validation(scope: str, valid: bool) -> None:
    config = YandexDriveConfig(client_id="id", client_secret="secret", oauth_scope=scope)
    if valid:
        config.validate()
        assert set(config.scopes) == {"cloud_api:disk.read", "cloud_api:disk.write"}
    else:
        with pytest.raises(ConfigurationError):
            config.validate()


@pytest.mark.parametrize(
    ("field", "value"),
    [("timeout", "bad"), ("timeout", 0), ("timeout", -1), ("download_chunk_size", "bad"), ("download_chunk_size", 0), ("download_chunk_size", -1)],
)
def test_invalid_numeric_settings(field: str, value: object) -> None:
    kwargs = {"client_id": "id", "client_secret": "secret", field: value}
    if value == "bad":
        with pytest.raises(ConfigurationError):
            YandexDriveConfig(**kwargs)  # type: ignore[arg-type]
    else:
        with pytest.raises(ConfigurationError):
            YandexDriveConfig(**kwargs).validate()  # type: ignore[arg-type]


def test_config_repr_hides_secret_and_missing_credentials_are_typed() -> None:
    config = YandexDriveConfig(client_secret="do-not-show")
    assert "do-not-show" not in repr(config)
    with pytest.raises(ConfigurationError, match="CLIENT_ID"):
        config.validate()
