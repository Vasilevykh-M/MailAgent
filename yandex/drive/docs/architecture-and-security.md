# Architecture and security

`YandexDriveConfig` loads and validates credentials, endpoint, positive timeout,
positive chunk size, and both required Drive scopes. `OAuthClient` only creates
authorization URLs and exchanges or refreshes tokens. `TokenStore` owns JSON
token persistence and replaces files atomically with restrictive permissions
where supported.

`YandexDriveApiClient` makes authenticated requests to the official Disk REST
API, then makes a separate request to the returned temporary transfer URL.
OAuth is sent only as `Authorization: OAuth <token>` to the main API. The
temporary download and upload requests do not receive that header and signed
URLs are never logged or included in exceptions.

`YandexDriveService` validates remote paths without changing them, supplies the
latest access token, and coordinates safe local transfers. It streams local
uploads and streamed downloads; downloaded destination paths use an atomic
temporary-file replacement. Temporary files are removed when any step fails.

Before a main REST request, an access token near expiry is refreshed. If a main
request returns `401`, the token is refreshed or reacquired and exactly one
request retry follows. Direct upload transfers are not retried because a partial
write can have an ambiguous result.

Sensitive values are hidden from model/config `repr` output. The SDK avoids
logging secrets, authorization codes, access or refresh tokens, signed URLs,
headers, OAuth bodies, token-file contents, and file content. `.env` and the
dedicated `.drive_tokens.json` are excluded by `.gitignore`.
