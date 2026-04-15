from __future__ import annotations

import os
import logging
from typing import IO, Any, Iterator

logger = logging.getLogger(__name__)

DEFAULT_ENCODING = "utf-8"

def validate_path(file_path: str) -> str:
    if ".." in os.path.normpath(file_path).split(os.sep):
        raise ValueError("Path file tidak valid (Potensi Path Traversal terdeteksi).")
    safe_path = os.path.abspath(file_path)
    if not os.path.exists(safe_path):
        raise FileNotFoundError(f"File tidak ditemukan: {safe_path}")
    return safe_path


def seek_to_start(stream: IO[bytes] | IO[str] | Any) -> None:
    try:
        stream.seek(0)
    except (AttributeError, OSError):
        pass


def iter_lines(
    file_or_path: str | IO[bytes] | IO[str] | Any,
    encoding: str = DEFAULT_ENCODING,
) -> Iterator[str]:
    if isinstance(file_or_path, str):
        safe_path = validate_path(file_or_path)
        with open(safe_path, "r", encoding=encoding, errors="strict") as fh:
            for line in fh:
                yield line.rstrip("\r\n")
    else:
        seek_to_start(file_or_path)
        for line in file_or_path:
            if isinstance(line, bytes):
                line_str = line.decode(encoding, errors="strict")
            else:
                line_str = line
            yield line_str.rstrip("\r\n")
