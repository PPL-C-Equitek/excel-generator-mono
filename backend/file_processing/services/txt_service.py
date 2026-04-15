from __future__ import annotations

import logging
from typing import IO, Any, Iterator

from file_processing.utils.io_utils import iter_lines, DEFAULT_ENCODING

logger = logging.getLogger(__name__)

def _read_lines(file_or_path: str | IO[bytes] | IO[str] | Any) -> Iterator[str]:
    yield from iter_lines(file_or_path, encoding=DEFAULT_ENCODING)

def parse_txt(
    file_or_path: str | IO[bytes] | IO[str] | Any,
    delimiter: str | None = None,
) -> list[list[str]]:
    if delimiter is None:
        return [[line] for line in _read_lines(file_or_path) if line]
    return [line.split(delimiter) for line in _read_lines(file_or_path) if line]


def parse_txt_with_delimiter(
    file_or_path: str | IO[bytes] | IO[str] | Any,
    delimiter: str = ",",
) -> list[list[str]]:
    return parse_txt(file_or_path, delimiter=delimiter)


def process_uploaded_txt(
    file_or_path: str | IO[bytes] | IO[str] | Any,
) -> tuple[bool, str | None, list[list[str]] | None]:
    try:
        data = parse_txt(file_or_path)
    except FileNotFoundError:
        return False, "File tidak ditemukan.", None
    except UnicodeDecodeError:
        return False, "File teks rusak atau format karakter tidak didukung.", None
    except Exception:
        logger.exception("TXT parsing failed")
        return False, "Invalid or unreadable TXT file.", None

    return True, None, data