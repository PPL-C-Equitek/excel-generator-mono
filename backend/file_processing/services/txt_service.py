from __future__ import annotations

import os
import logging
from typing import IO, Any

logger = logging.getLogger(__name__)

DEFAULT_ENCODING = "utf-8"

def _read_lines(file_or_path: str | IO[bytes] | IO[str] | Any) -> list[str]:
    if isinstance(file_or_path, str):
        if not os.path.exists(file_or_path):
            raise FileNotFoundError(f"File tidak ditemukan: {file_or_path}")

        with open(file_or_path, "r", encoding=DEFAULT_ENCODING, errors="replace") as fh:
            raw = fh.read()
    else:
        try:
            file_or_path.seek(0)
        except (AttributeError, OSError):
            pass

        content = file_or_path.read()
        if isinstance(content, bytes):
            raw = content.decode(DEFAULT_ENCODING, errors="replace")
        else:
            raw = content

    if not raw and raw != "":
        raise ValueError("File tidak dapat dibaca.")

    return raw.splitlines()

def parse_txt(
    file_or_path: str | IO[bytes] | IO[str] | Any,
) -> list[list[str]]:
    lines = _read_lines(file_or_path)

    return [
        [line]
        for line in lines
        if line
    ]

def parse_txt_with_delimiter(
    file_or_path: str | IO[bytes] | IO[str] | Any,
    delimiter: str = ",",
) -> list[list[str]]:
    lines = _read_lines(file_or_path)

    return [
        line.split(delimiter)
        for line in lines
        if line
    ]

def process_uploaded_txt(
    file_or_path: str | IO[bytes] | IO[str] | Any,
) -> tuple[bool, str | None, list[list[str]] | None]:
    try:
        data = parse_txt(file_or_path)
    except FileNotFoundError as exc:
        return False, str(exc), None
    except Exception:
        logger.exception("TXT parsing failed")
        return False, "Invalid or unreadable TXT file.", None

    return True, None, data