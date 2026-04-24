import csv
import logging
from typing import IO, Any

from file_processing.utils.io_utils import validate_path, seek_to_start

logger = logging.getLogger(__name__)

DEFAULT_ENCODING = "utf-8-sig"

def _read_lines_from_file(file_or_path: str | IO[bytes] | IO[str] | Any):
    if isinstance(file_or_path, str):
        safe_path = validate_path(file_or_path)
        with open(safe_path, "r", encoding=DEFAULT_ENCODING, errors="strict") as fh:
            yield from fh.readlines()
    else:
        seek_to_start(file_or_path)
        for line in file_or_path:
            if isinstance(line, bytes):
                line_str = line.decode(DEFAULT_ENCODING, errors="strict")
            else:
                line_str = line
            yield line_str

def _make_unique_headers(headers: list[str]) -> list[str]:
    seen = {}
    unique_headers = []
    for h in headers:
        if h in seen:
            seen[h] += 1
            unique_headers.append(f"{h}_{seen[h]}")
        else:
            seen[h] = 0
            unique_headers.append(h)
    return unique_headers

def _process_row(row: list[str], fieldnames: list[str], strict: bool) -> dict | None:
    if not row:
        return None

    if strict and len(row) != len(fieldnames):
        raise ValueError(f"Mismatched column count. Expected {len(fieldnames)}, got {len(row)}")

    row_dict = {}
    for i, key in enumerate(fieldnames):
        val = row[i] if i < len(row) else ""
        row_dict[key] = val
    return row_dict

def parse_csv(file_or_path: str | IO[bytes] | IO[str] | Any, delimiter: str = ",", strict: bool = False) -> list[dict]:
    if file_or_path is None:
        raise TypeError("file_or_path cannot be None")

    try:
        lines_iter = _read_lines_from_file(file_or_path)
        reader = csv.reader(lines_iter, delimiter=delimiter)

        try:
            head_row = next(reader)
        except StopIteration:
            return []

        if not head_row:
            return []

        fieldnames = _make_unique_headers(head_row)

        result = []
        for row in reader:
            row_dict = _process_row(row, fieldnames, strict)
            if row_dict is not None:
                result.append(row_dict)

        return result

    except UnicodeDecodeError:
        raise
    except Exception:
        logger.exception("Failed to parse CSV")
        raise


def process_uploaded_csv(file_or_path):
    try:
        raw = None
        if isinstance(file_or_path, str):
            safe_path = validate_path(file_or_path)
            with open(safe_path, "rb") as fh:
                raw = fh.read()
        else:
            try:
                file_or_path.seek(0)
                raw = file_or_path.read()
                file_or_path.seek(0)
            except (AttributeError, OSError):
                pass

        if raw is not None and not raw.strip():
            return False, "CSV file is empty or does not contain valid data.", None

        data = parse_csv(file_or_path)
        return True, None, data

    except UnicodeDecodeError:
        return False, "CSV file is corrupted or character format is not supported.", None

    except Exception:
        logger.exception("CSV parsing failed")
        return False, "Invalid or unreadable CSV file.", None
