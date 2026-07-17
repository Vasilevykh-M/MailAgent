from __future__ import annotations

from collections import deque
from typing import Any


class FakeResponse:
    def __init__(
        self,
        *,
        status_code: int = 200,
        body: Any = None,
        content: bytes = b"",
        chunks: list[bytes] | None = None,
        json_error: bool = False,
    ) -> None:
        self.status_code = status_code
        self._body = body
        self.content = content
        self._chunks = chunks if chunks is not None else [content]
        self._json_error = json_error
        self.closed = False

    @property
    def ok(self) -> bool:
        return 200 <= self.status_code < 300

    def json(self) -> Any:
        if self._json_error:
            raise ValueError("invalid JSON")
        return self._body

    def iter_content(self, *, chunk_size: int):
        self.chunk_size = chunk_size
        yield from self._chunks

    def close(self) -> None:
        self.closed = True


class FakeSession:
    def __init__(self, responses: list[FakeResponse | Exception]) -> None:
        self.responses = deque(responses)
        self.calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []

    def request(self, *args: Any, **kwargs: Any) -> FakeResponse:
        self.calls.append((args, kwargs))
        response = self.responses.popleft()
        if isinstance(response, Exception):
            raise response
        return response

    def post(self, *args: Any, **kwargs: Any) -> FakeResponse:
        return self.request(*args, **kwargs)
