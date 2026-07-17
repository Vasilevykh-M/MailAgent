"""Request-id validation and access helpers."""

from __future__ import annotations

import re
import uuid

from starlette.requests import Request

_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


def request_id_from_header(value: str | None) -> str:
    if value and _REQUEST_ID_RE.fullmatch(value):
        return value
    return str(uuid.uuid4())


def get_request_id(request: Request) -> str:
    return getattr(request.state, "request_id", str(uuid.uuid4()))
