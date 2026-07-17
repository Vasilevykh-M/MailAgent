"""Межпроцессная блокировка одного ядра на одну SQLite БД."""

from __future__ import annotations

import os
from pathlib import Path
from typing import TextIO

from ..exceptions import ConfigurationError


class CoreWorkerLock:
    def __init__(self, db_path: Path) -> None:
        self.path = db_path.with_suffix(db_path.suffix + ".lock")
        self._handle: TextIO | None = None

    def acquire(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle = self.path.open("a+")
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)  # type: ignore[attr-defined]
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            handle.close()
            raise ConfigurationError("Другой core worker уже использует эту SQLite БД.") from exc
        self._handle = handle

    def release(self) -> None:
        if self._handle is None:
            return
        handle = self._handle
        try:
            if os.name != "nt":
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()
            self._handle = None

    def __enter__(self) -> CoreWorkerLock:
        self.acquire()
        return self

    def __exit__(self, *_: object) -> None:
        self.release()
