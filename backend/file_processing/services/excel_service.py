from __future__ import annotations

import os
from typing import Any, IO
from openpyxl.utils.exceptions import InvalidFileException
from zipfile import BadZipFile

def _load_workbook(file_or_path: str | IO[bytes] | Any):
    try:
        from openpyxl import load_workbook
    except ImportError as exc:
        raise RuntimeError(
            "openpyxl tidak terinstall. Jalankan: pip install openpyxl"
        ) from exc

    if isinstance(file_or_path, str) and not os.path.exists(file_or_path):
        raise FileNotFoundError(f"File tidak ditemukan: {file_or_path}")

    try:
        wb = load_workbook(file_or_path, read_only=True, data_only=True)
        return wb
    except Exception as exc:
        raise ValueError(
            f"File Excel corrupted atau cannot read: {exc}"
        ) from exc

def _sheet_to_rows(ws) -> list[list[Any]]:
    raw_rows = list(ws.iter_rows(values_only=True))

    if not raw_rows:
        return []
    
    data_rows: list[list[Any]] = []
    for row in raw_rows:
        row_list = list(row)

        null_count = 0
        while row_list and (row_list[-1] is None or row_list[-1] == ""):
            row_list.pop()
            null_count += 1
            
        if not row_list and null_count == len(row):
            continue

        if null_count > 1:
            row_list.append(f"nullx{null_count}")
        elif null_count == 1:
            row_list.append("null")
            
        data_rows.append(row_list)

    return data_rows

def parse_excel(file_or_path: str | IO[bytes] | Any) -> dict[str, list[list[Any]]]:
    wb = _load_workbook(file_or_path)

    result: dict[str, list[list[Any]]] = {}
    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        result[sheet_name] = _sheet_to_rows(ws)

    wb.close()
    return result

def process_uploaded_excel(
    file_or_path: str | IO[bytes] | Any,
) -> tuple[bool, str | None, dict[str, list[list[Any]]] | None]:

    try:
        data = parse_excel(file_or_path)

    except FileNotFoundError as exc:
        return False, str(exc), None

    except (ValueError, InvalidFileException, BadZipFile):
        return False, "Invalid or corrupted Excel file.", None

    return True, None, data