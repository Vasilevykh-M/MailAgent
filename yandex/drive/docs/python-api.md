# Python API

The principal entry point is `YandexDriveService`:

```python
from pathlib import Path
from yandex_drive import YandexDriveConfig, YandexDriveService

config = YandexDriveConfig(
    client_id="client-id",
    client_secret="client-secret",
    token_file=Path(".drive_tokens.json"),
)
service = YandexDriveService(config)
```

Or load a dotenv file:

```python
service = YandexDriveService.from_env(".env")
resource = service.get_metadata("/photos")
raw = service.download_file("/documents/report.pdf")
saved = service.download_file_to("/backups/archive.zip", Path("downloads/archive.zip"))
uploaded = service.upload_file(Path("image.png"), "/photos/image.png", overwrite=True)
copy = service.upload_bytes(raw, "/documents/report-copy.pdf", overwrite=True)
```

All methods return a result or raise a subclass of `YandexDriveError`; none
prints to stdout. `DiskResource` represents either `file` or `dir` metadata
and provides `to_dict()` for JSON-compatible serialization.

For tests or hosted applications, inject collaborators:

```python
service = YandexDriveService(
    config,
    token_store=fake_token_store,
    oauth_client=fake_oauth_client,
    api_client=fake_api_client,
)
```

The default API client can instead receive an injected `requests.Session`.
OAuth code input and authorization URL output are replaceable callbacks.
