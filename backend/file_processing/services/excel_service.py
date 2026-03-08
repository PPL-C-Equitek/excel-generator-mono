from __future__ import annotations

import os
from typing import Any, IO

def _load_workbook(file_or_path: str | IO[bytes] | Any):
    try:
        from openpyxl import load_workbook
    except ImportError as exc:
        raise RuntimeError(
            "openpyxl tidak terinstall. Jalankan: pip install openpyxl"
        ) from exc

    if isinstance(file_or_path, str):
        if not os.path.exists(file_or_path):
            raise FileNotFoundError(f"File tidak ditemukan: {file_or_path}")

    try:
        wb = load_workbook(file_or_path, read_only=True, data_only=True)
        return wb
    except Exception as exc:
        raise ValueError(
            f"File Excel corrupted atau cannot read: {exc}"
        ) from exc

def _find_header_row_index(raw_rows: list, min_string_cols: int = 2) -> int:
    for idx, row in enumerate(raw_rows):
        string_cols = sum(
            1 for cell in row
            if cell is not None and isinstance(cell, str) and cell.strip() != ""
        )
        if string_cols >= min_string_cols:
            return idx
    return 0

def _sheet_to_rows(ws) -> list[dict[str, Any]]:
    raw_rows = list(ws.iter_rows(values_only=True))

    if not raw_rows:
        return []

    header_idx = _find_header_row_index(raw_rows)
    header_row = raw_rows[header_idx]
    headers = [
        (str(h) if h is not None else "") for h in header_row
    ]

    data_rows: list[dict[str, Any]] = []
    for row in raw_rows[header_idx + 1:]:
        if all(cell is None for cell in row):
            continue
        row_dict: dict[str, Any] = {}
        for col_idx, header in enumerate(headers):
            value = row[col_idx] if col_idx < len(row) else None
            row_dict[header] = value
        data_rows.append(row_dict)

    return data_rows

def parse_excel(file_or_path: str | IO[bytes] | Any) -> dict[str, list[dict[str, Any]]]:
    wb = _load_workbook(file_or_path)

    result: dict[str, list[dict[str, Any]]] = {}
    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        result[sheet_name] = _sheet_to_rows(ws)

    wb.close()
    return result

def process_uploaded_excel(
    file_or_path: str | IO[bytes] | Any,
) -> tuple[bool, str | None, dict[str, list[dict[str, Any]]] | None]:

    try:
        data = parse_excel(file_or_path)
    except (ValueError, FileNotFoundError) as exc:
        return False, str(exc), None

    return True, None, data