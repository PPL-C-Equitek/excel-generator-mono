from __future__ import annotations

import os
import logging
from typing import IO, Any, Iterator

logger = logging.getLogger(__name__)

DEFAULT_ENCODING = "utf-8"

def _read_lines_from_path(file_path: str) -> Iterator[str]:
    if ".." in os.path.normpath(file_path).split(os.sep):
        raise ValueError("Path file tidak valid (Potensi Path Traversal terdeteksi).")

    safe_path = os.path.abspath(file_path)

    if not os.path.exists(safe_path):
        raise FileNotFoundError(f"File tidak ditemukan: {safe_path}")

    with open(safe_path, "r", encoding=DEFAULT_ENCODING, errors="strict") as fh:
        for line in fh:
            yield line.rstrip('\r\n')


def _read_lines_from_stream(stream: IO[bytes] | IO[str] | Any) -> Iterator[str]:
    try:
        stream.seek(0)
    except (AttributeError, OSError):
        pass

    for line in stream:
        if isinstance(line, bytes):
            line_str = line.decode(DEFAULT_ENCODING, errors="strict")
        else:
            line_str = line
        
        yield line_str.rstrip('\r\n')


def _read_lines(file_or_path: str | IO[bytes] | IO[str] | Any) -> Iterator[str]:
    if isinstance(file_or_path, str):
        yield from _read_lines_from_path(file_or_path)
    else:
        yield from _read_lines_from_stream(file_or_path)

def parse_txt(
    file_or_path: str | IO[bytes] | IO[str] | Any) -> list[list[str]]:

    return [
        [line]
        for line in _read_lines(file_or_path)
        if line
    ]

def parse_txt_with_delimiter(
    file_or_path: str | IO[bytes] | IO[str] | Any,
    delimiter: str = ",",
) -> list[list[str]]:
    return [
        line.split(delimiter)
        for line in _read_lines(file_or_path)
        if line
    ]

def process_uploaded_txt(
    file_or_path: str | IO[bytes] | IO[str] | Any,
) -> tuple[bool, str | None, list[list[str]] | None]:
    try:
        data = parse_txt(file_or_path)
    except FileNotFoundError as exc:
        return False, str(exc), None
    except UnicodeDecodeError:
        return False, "File teks rusak atau format karakter tidak didukung.", None
    except Exception:
        logger.exception("TXT parsing failed")
        return False, "Invalid or unreadable TXT file.", None

    return True, None, data