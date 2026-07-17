# Getting started

Install from this directory with Python 3.11 or newer:

```bash
python -m venv .venv
source .venv/bin/activate                 # Windows: .venv\Scripts\Activate.ps1
python -m pip install -e .
```

Create an OAuth application through Yandex, request `cloud_api:disk.read` and
`cloud_api:disk.write`, and use the redirect URI
`https://oauth.yandex.ru/verification_code`. These are the Drive permissions
used by the [official REST API](https://yandex.com/dev/disk-api/doc/en/).

Copy the safe template and configure only local values:

```bash
cp .env.example .env
yandex-drive auth
```

The SDK reads `.env` without mutating the process environment; actual process
variables take precedence. `YANDEX_DRIVE_CLIENT_ID` and
`YANDEX_DRIVE_CLIENT_SECRET` have priority over their generic `YANDEX_*`
fallbacks. The token file defaults to `.drive_tokens.json` and a relative path
is resolved against the `.env` file directory.

Drive tokens are separate from Mail tokens. A token issued for mail may not
carry the required Disk scopes, even if the same OAuth client ID is used.
