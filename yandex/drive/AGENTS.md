# Agent Instructions: Yandex Drive SDK

## Scope

These rules apply to all of `yandex/drive/` and supplement the root
`AGENTS.md`. Work only within this directory unless the user explicitly requests
a different scope.

`yandex-drive-sdk` is a standalone Python package for the Yandex Disk REST API:

- distribution name: `yandex-drive-sdk`;
- importable package: `yandex_drive`;
- CLI: `yandex-drive`;
- minimum Python version: 3.11;
- package layout: `src/yandex_drive/`.

Do not add dependencies, imports, or shared modules with `yandex/mail/`.
`yandex_mail` must not be imported by `yandex_drive`, and `yandex_drive` must
not be imported by `yandex_mail`.

## Protecting the Yandex Mail SDK

For any task in `yandex/drive/`, the `../mail/` directory is entirely
read-only. Do not modify its source code, tests, documentation, `pyproject.toml`,
`.env.example`, `.gitignore`, `.env`, token files, caches, or package metadata.

The Mail SDK may be studied as an architectural reference. Its tests may be run
only without writing bytecode or pytest cache files. Do not extract shared code
between the packages, alter Mail's public API, or make Drive a Mail dependency.

## Module structure and responsibilities

Preserve the separation of concerns:

| Module | Responsibility |
| --- | --- |
| `config.py` | `.env`, environment variables, scope normalization, and settings validation. |
| `oauth.py` | Authorization URL, verification-code exchange, refresh token, and safe OAuth error normalization. |
| `token_store.py` | `OAuthToken` model, JSON storage, and atomic token writes. |
| `api_client.py` | Low-level REST requests, temporary URLs, HTTP errors, and one retry after `401`. |
| `models.py` | HTTP-independent, JSON-compatible models including `DiskResource`. |
| `service.py` | Embeddable public API, path validation, safe local files, and component orchestration. |
| `cli.py` | Thin `argparse` layer, safe output formatting, and process exit codes. |
| `exceptions.py` | Typed exception hierarchy. |

Do not move business logic into the CLI. Do not perform network requests, read
stdin, or authorize with OAuth while importing `yandex_drive`. Public service
methods must not print to stdout.

## OAuth, configuration, and secrets

- Use only Drive-specific OAuth scopes: `cloud_api:disk.read` and
  `cloud_api:disk.write`.
- `YANDEX_DRIVE_CLIENT_ID` and `YANDEX_DRIVE_CLIENT_SECRET` take precedence over
  the fallback variables `YANDEX_CLIENT_ID` and `YANDEX_CLIENT_SECRET`.
- Never use `YANDEX_OAUTH_SCOPE` as a fallback because it may contain Mail
  permissions. Normalize only `YANDEX_DRIVE_OAUTH_SCOPE`.
- Use a dedicated `.drive_tokens.json` file, never Mail's `.tokens.json`.
- Resolve a relative token-file path from the `.env` directory.
- Never print or log the Client Secret, access/refresh token, verification code,
  complete `Authorization` header, token-file contents, signed URL, or file
  contents.
- Hide sensitive fields from `repr` and exclude them from exception text.
- Do not create or edit user-owned `.env` or `.drive_tokens.json` files without
  a separate user instruction.

Write tokens atomically only: create a temporary file in the same directory,
write JSON, `flush`, `fsync`, apply `0600` where supported, and call
`os.replace`. Remove the temporary file after every failure.

## Yandex Disk API rules

- Use the official REST API directly through `requests`; do not add unofficial
  SDK wrappers.
- The base API URL is `https://cloud-api.yandex.net/v1/disk`.
- Send the access token only to the main API in the
  `Authorization: OAuth <access_token>` header.
- Pass a Disk path through `params={"path": remote_path}`. Do not manually
  build a query string or normalize a remote path with local OS path rules.
- Support `/path` and `disk:/path`; empty or whitespace-only paths must raise
  `InvalidRemotePathError`.
- Use `GET /resources` for metadata and `GET /resources/download` /
  `GET /resources/upload` for temporary URLs.
- Do not automatically send the OAuth header to temporary URLs or log them.
- For every successful upload, accept documented `2xx` statuses, then retrieve
  metadata and return a `DiskResource`.
- After a `401` from the main API, refresh/reacquire the token and retry exactly
  once. If the second response is `401`, raise `AuthenticationError`.
- Never retry a direct transfer to a temporary URL when its partial result could
  be ambiguous.

## File handling

All files are opaque binary data. Do not parse, decompress, modify, or validate
them by format, extension, or MIME type. Empty files and names without
extensions are mandatory supported cases.

- Use `download_file` only when the full file fits in memory; it must return the
  exact response `bytes`.
- `download_file_to` must use `stream=True`, the configured chunk size, a
  temporary file in the destination directory, `fsync`, and `os.replace` only
  after complete success. Do not replace an existing file without
  `overwrite=True`.
- `upload_file` accepts only an existing local regular file and passes an open
  binary file object as a stream without reading the complete file into memory.
- `upload_bytes` accepts only `bytes`, `bytearray`, or `memoryview`, and uses an
  in-memory binary stream without a persistent temporary file.
- Local path failures must be `LocalFileError`; HTTP failures must map to the
  exceptions in `exceptions.py` without exposing data.

## Tests and verification

Tests belong only in `tests/`. They must be deterministic and must not contact
real OAuth services or a user's Disk. Use fake/mocked `requests.Session`
instances, responses, token stores, OAuth clients, temporary directories, and
dependency injection.

After changing code, create/activate an isolated environment and run:

```bash
cd yandex/drive
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
pytest
yandex-drive --help
python -c "from yandex_drive import YandexDriveService"
python -c "import yandex_drive, sys; assert 'yandex_mail' not in sys.modules"
```

Do not leave `.venv/`, `.pytest_cache/`, `__pycache__/`, `*.egg-info/`, or
other reproducible installation artifacts in the project. They are ignored by
`.gitignore` and may be removed after verification if they contain no user data.

## Documentation and final report

Write README and user-facing documents in Russian. Do not translate commands,
file names, URLs, JSON fields, environment variables, import names, or API
methods. When external behavior changes, update `README.md` and the relevant
files in `docs/`.

The final response must state:

1. changed files and implemented behavior;
2. checks performed and their actual results;
3. checks not performed and why;
4. that no real OAuth/Drive requests were made if only mocks were used;
5. confirmation that `yandex/mail/` was not modified when the task concerns
   Drive.
