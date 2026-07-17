"""Small security and serialization helpers."""

from __future__ import annotations

from pathlib import Path
import os
import re
from typing import Iterable

from .exceptions import AttachmentSaveError


_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")


def sanitize_filename(filename: str | None, *, default: str = "attachment") -> str:
    """Return a platform-safe basename, never a path supplied by a sender."""

    candidate = (filename or default).replace("\\", "/")
    candidate = _CONTROL_CHARS.sub("", candidate)
    # basename deliberately strips absolute paths and all ../ components.
    candidate = candidate.rsplit("/", 1)[-1].strip().rstrip(". ")
    if candidate in {"", ".", ".."}:
        candidate = default
    # Windows does not permit these characters. Keeping this portable avoids
    # surprising failures when an attachment directory is moved between OSes.
    candidate = re.sub(r'[<>:"|?*]', "_", candidate)
    if candidate.upper().split(".", 1)[0] in {
        "CON", "PRN", "AUX", "NUL", "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
        "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
    }:
        candidate = "_" + candidate
    return candidate[:240] or default


def safe_save_bytes(directory: str | Path, filename: str | None, data: bytes, *, overwrite: bool = False) -> Path:
    """Save bytes below *directory* without path traversal or accidental overwrite."""

    root = Path(directory).expanduser().resolve()
    try:
        root.mkdir(parents=True, exist_ok=True)
        name = sanitize_filename(filename)
        destination = (root / name).resolve()
        if os.path.commonpath([str(root), str(destination)]) != str(root):
            raise AttachmentSaveError("Attachment path escapes the selected output directory.")
        if not overwrite:
            stem, suffix = destination.stem, destination.suffix
            number = 2
            while destination.exists():
                destination = root / f"{stem}_{number}{suffix}"
                number += 1
        mode = "wb" if overwrite else "xb"
        with destination.open(mode) as handle:
            handle.write(data)
        return destination
    except AttachmentSaveError:
        raise
    except OSError as exc:
        raise AttachmentSaveError("Could not save attachment safely.") from exc


def chunks(values: Iterable[str], size: int) -> Iterable[list[str]]:
    """Yield lists of at most *size* items."""

    if size <= 0:
        raise ValueError("Batch size must be positive.")
    batch: list[str] = []
    for value in values:
        batch.append(value)
        if len(batch) == size:
            yield batch
            batch = []
    if batch:
        yield batch


def format_size(size: int) -> str:
    """Format a byte size for compact terminal output."""

    units = ("B", "KB", "MB", "GB")
    value = float(size)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{int(value)} {unit}" if unit == "B" else f"{value:.0f} {unit}"
        value /= 1024
    return f"{size} B"
