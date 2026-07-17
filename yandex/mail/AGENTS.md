# Agent Instructions: Yandex Mail SDK

## Scope

These instructions apply only to `yandex/mail/` and take precedence over the
root `AGENTS.md` for every file in this SDK. Yandex Mail is an independent
Python package; do not couple it to `yandex/drive`, `ocr-service`, or
`llm-service` without an explicit user request.

Work only on files necessary for the task in this directory. Do not relocate the
SDK, add shared root-level configuration, or fix another SDK under `yandex/` as
incidental work.

## Project map

```text
yandex/mail/
├── pyproject.toml              # package metadata, dependencies, and console script
├── .env.example                # safe configuration template
├── README.md                   # concise Russian-language guide
├── docs/                       # detailed Russian-language documentation
├── src/yandex_mail/
│   ├── __init__.py             # public imports
│   ├── config.py               # YandexMailConfig and .env loading
│   ├── oauth.py                # OAuth Authorization Code Flow and refresh grant
│   ├── token_store.py          # OAuthToken and atomic token persistence
│   ├── imap_client.py          # SSL/TLS, XOAUTH2, and UID IMAP transport
│   ├── parser.py               # RFC 5322/MIME parsing
│   ├── models.py               # Attachment, MessageStatus, Summary, MailMessage, Page
│   ├── service.py              # YandexMailService high-level API
│   ├── cli.py                  # yandex-mail command
│   ├── exceptions.py           # public exception hierarchy
│   └── utils.py                # safe file operations and helpers
└── tests/                      # isolated pytest tests without a real account
```

Before changing anything, read `README.md`, the relevant document in `docs/`,
`pyproject.toml`, the code in the affected layer, and its tests. For external
contracts, use `docs/cli.md` and `docs/python-api.md` as references.

## Public contract

The primary public imports must remain available from `yandex_mail`:

```python
from yandex_mail import YandexMailConfig, YandexMailService
```

The main service-construction path is:

```python
service = YandexMailService.from_env(".env")
```

Do not change exported class names, public method signatures, CLI command names,
JSON keys, or status values without a direct user request. For an approved
contract change, update all of the following:

1. implementation and type annotations;
2. tests;
3. `README.md`;
4. the relevant document in `docs/`.

Keep UIDs as message identifiers. Do not substitute sequence numbers for UIDs:
sequence numbers can change after mailbox operations.

## Configuration and secrets

Supported environment variables are listed in `.env.example`:

```dotenv
YANDEX_CLIENT_ID=
YANDEX_CLIENT_SECRET=
YANDEX_EMAIL=
YANDEX_REDIRECT_URI=https://oauth.yandex.ru/verification_code
YANDEX_OAUTH_SCOPE=mail:imap_full
YANDEX_IMAP_HOST=imap.yandex.com
YANDEX_IMAP_PORT=993
YANDEX_IMAP_MAILBOX=INBOX
YANDEX_TOKEN_FILE=.tokens.json
```

Required invariants:

- The redirect URI is `https://oauth.yandex.ru/verification_code`.
- The scope is `mail:imap_full`, because the SDK modifies IMAP flags.
- Default IMAP is `imap.yandex.com:993` over SSL/TLS.
- A relative token-file path is resolved relative to `.env`.
- Process environment values override `.env` values.

Never commit real `.env` or `.tokens.json` files. Do not put a Client Secret,
access token, refresh token, verification code, complete XOAUTH2 payload, or
contents of real messages into logs, exceptions, documentation, or test
snapshots. Tests must use fake values and mock/fake objects.

## OAuth and token storage

OAuth is implemented exclusively through Yandex's Authorization Code Flow:

1. build the `/authorize` URL with `response_type=code`, Client ID, redirect URI,
   and scope;
2. receive the verification code entered by the user;
3. exchange the code for `access_token` and `refresh_token` through `/token`;
4. persist tokens locally;
5. refresh the access token before expiry;
6. replace the refresh token when the server provides a new one;
7. start a new interactive authorization flow when a refresh token is invalid.

`TokenStore` must persist tokens atomically: create the temporary file in the
same directory, write and sync it, then replace the destination through
`os.replace()`. Preserve mode `0600` where supported and cross-platform
behavior on Windows, Linux, and macOS.

Do not expose tokens in a dataclass `repr`, debug logs, or error text. Corrupted
token JSON must raise `TokenStorageError`, not silently discard state.

## IMAP and XOAUTH2

Use the standard-library `imaplib.IMAP4_SSL`. The XOAUTH2 callback returns
**raw bytes**, not Base64:

```text
user=<email>\x01auth=Bearer <access_token>\x01\x01
```

`imaplib.authenticate()` Base64-encodes the callback value itself. Do not add
manual Base64 encoding.

Transport-layer requirements:

- open one connection per high-level operation and log out correctly on cleanup;
- select the mailbox explicitly and report `MailboxError` on failure;
- map timeouts, dropped connections, and IMAP errors to domain exceptions;
- on XOAUTH2 failure, refresh the access token and retry authentication exactly
  once; a second failure raises `ImapAuthenticationError`;
- do not open a separate IMAP connection for every message;
- use `UID SEARCH`, `UID FETCH`, and `UID STORE`, rather than sequence-number
  commands, to address messages.

Do not create infinite retry loops or hide server-side authentication errors.

## Lists, statuses, and flags

### Listing messages

`list_messages()` and `iter_messages()` must remain efficient:

1. execute IMAP-supported filters through `UID SEARCH`;
2. fetch metadata through batched `UID FETCH` calls;
3. request only UID, FLAGS, size, INTERNALDATE, and necessary headers for a
   normal list, never the full MIME body;
4. control batch size with `batch_size`;
5. do not keep every `MessageSummary` in memory in the generator.

Supported statuses are `all`, `read`, `unread`, `important`, `not-important`,
`answered`, `unanswered`, `draft`, `deleted`, and `recent`. Preserve
compatibility with `unread_only=True`; conflicting `status` values must produce
a clear error.

Do not calculate an exact attachment count by downloading every MIME message for
an ordinary list. Standard IMAP has no universal "has attachment" criterion;
the `Content-Type` filter remains a server-side approximation and must be
documented as such.

### Flags

System flags are matched case-insensitively:

| Flag | Model field |
| --- | --- |
| `\Seen` | `is_read`; absence means `is_unread` |
| `\Flagged` | `is_important` |
| `\Answered` | `is_answered` |
| `\Draft` | `is_draft` |
| `\Deleted` | `is_deleted` |
| `\Recent` | `is_recent` |

Do not discard custom IMAP keywords: retain them in `custom_flags`. After
`UID STORE`, always fetch `(UID FLAGS)` again and return server-confirmed
`MessageStatus`. Reject adding and removing the same flag in one operation, and
validate UIDs and flags before issuing a request.

Bulk operations should use one UID set and one `UID STORE` where possible, while
correctly reporting absent UIDs and partial outcomes.

## MIME, messages, and attachments

Use the standard `email` package; do not replace it with an unreviewed external
library. The MIME parser must correctly handle:

- `text/plain`, `text/html`, HTML-only messages, and messages without a body;
- `multipart/alternative`, `multipart/mixed`, `multipart/related`, and nested
  multipart structures;
- Base64, quoted-printable, missing charsets, and unknown charsets;
- RFC 2047-encoded and Unicode headers;
- regular and inline attachments;
- repeated headers in their original order.

Preserve both body versions, preferring `text_plain` in text output. Attachment
contents must not appear in `text_plain` or `text_html`. For an unknown charset,
use a safe fallback with `errors="replace"`.

### Safe file storage

When saving an attachment, always:

- use only the basename and remove `../`, `..\`, absolute paths, and control
  characters;
- verify that the normalized path remains below the selected directory;
- preserve the file extension;
- avoid overwriting existing files by default;
- generate `name_2.ext`, `name_3.ext`, and so on upon conflicts;
- map file-system errors to `AttachmentSaveError` without exposing attachment
  data.

`MailMessage.save_eml()` saves original RFC 5322 bytes. JSON serialization must
include `raw_bytes` and `Attachment.data` only through explicit opt-in and in
Base64.

## CLI

The `yandex-mail` console script and its commands are a public contract:

```text
diagnose
auth [--force]
list
status UID [UID ...]
read UID
attachments UID --output DIRECTORY
mark-read UID [UID ...]
mark-unread UID [UID ...]
mark-important UID [UID ...]
mark-not-important UID [UID ...]
```

Preserve the global `--env`, `--verbose`, and `--debug` options. Without
`--debug`, the CLI displays a clear error without a traceback and returns a
nonzero status code. With `--debug`, a traceback is acceptable, but secrets must
still never be displayed.

`diagnose` must not make OAuth or IMAP connections and must not print Client
Secret or token values. JSON output excludes attachment binary data and original
message bytes by default.

## Tests and verification

Tests must not connect to a real Yandex account, OAuth endpoint, or IMAP server.
Mock or fake all HTTP and IMAP interactions.

When changing a layer, extend the appropriate tests in `tests/`:

| Area | Minimum coverage |
| --- | --- |
| `config.py` | `.env` values, environment precedence, validation |
| `oauth.py` | URL, code exchange, refresh, no secrets in errors |
| `token_store.py` | read, atomic write, corrupted JSON, expiration |
| `imap_client.py` | raw XOAUTH2 without manual Base64, auth retry, UID commands |
| `parser.py` | multipart, charsets, headers, attachments, `.eml` |
| `service.py` | search, batched fetch, flags, pagination, UID errors |
| `cli.py` | help, diagnose, option conflicts, JSON, exit code |

Recommended checks from `yandex/mail/`:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
pytest
python -c "from yandex_mail import YandexMailService; print('import ok')"
yandex-mail --help
yandex-mail --env .env.example diagnose
```

Do not claim that real OAuth authorization or Yandex Mail access was verified
unless the user provided test credentials and explicitly requested that check.

## Documentation and final report

SDK documentation is written in Russian. Do not translate actual commands, file
names, URLs, JSON field names, environment variables, IMAP flags, or CLI values.

When behavior changes, update these files as needed:

- `README.md` — overview, installation, and primary examples;
- `docs/getting-started.md` — OAuth and `.env` setup;
- `docs/cli.md` — command options and examples;
- `docs/python-api.md` — public methods, models, and exceptions;
- `docs/architecture-and-security.md` — internal invariants and limitations;
- `docs/README.md` — documentation navigation.

In the final report, state:

1. what changed;
2. which tests and verification commands ran and their results;
3. which checks did not run and why;
4. that the change scope is `yandex/mail/`;
5. that live OAuth/IMAP integration was not verified, if applicable.
