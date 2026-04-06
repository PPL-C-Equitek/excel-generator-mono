from __future__ import annotations

import os
import logging
from typing import IO, Any, Iterator

logger = logging.getLogger(__name__)

DEFAULT_ENCODING = "utf-8"

def _read_lines(file_or_path: str | IO[bytes] | IO[str] | Any) -> Iterator[str]:
    if isinstance(file_or_path, str):
        if not os.path.exists(file_or_path):
            raise FileNotFoundError(f"File tidak ditemukan: {file_or_path}")

        with open(file_or_path, "r", encoding=DEFAULT_ENCODING, errors="strict") as fh:
            for line in fh:
                yield line.rstrip('\r\n')
    else:
        try:
            file_or_path.seek(0)
        except (AttributeError, OSError):
            pass

        for line in file_or_path:
            if isinstance(line, bytes):
                line_str = line.decode(DEFAULT_ENCODING, errors="strict")
            else:
                line_str = line
            
            yield line_str.rstrip('\r\n')

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