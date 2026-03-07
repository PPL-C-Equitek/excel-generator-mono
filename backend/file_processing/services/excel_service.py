from __future__ import annotations

import os
from typing import Any

def _load_workbook(file_path: str):
    try:
        from openpyxl import load_workbook  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "openpyxl tidak terinstall. Jalankan: pip install openpyxl"
        ) from exc

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File tidak ditemukan: {file_path}")

    try:
        wb = load_workbook(file_path, read_only=True, data_only=True)
        return wb
    except Exception as exc:
        raise ValueError(
            f"File Excel corrupted atau cannot read: {exc}"
        ) from exc


def _sheet_to_rows(ws) -> list[dict[str, Any]]:
    raw_rows = list(ws.iter_rows(values_only=True))

    if not raw_rows:
        return []

    header_row = raw_rows[0]
    headers = [
        (str(h) if h is not None else "") for h in header_row
    ]

    data_rows: list[dict[str, Any]] = []
    for row in raw_rows[1:]:
        row_dict: dict[str, Any] = {}
        for col_idx, header in enumerate(headers):
            value = row[col_idx] if col_idx < len(row) else None
            row_dict[header] = value
        data_rows.append(row_dict)

    return data_rows


def parse_excel(file_path: str) -> dict[str, list[dict[str, Any]]]:
    wb = _load_workbook(file_path)

    result: dict[str, list[dict[str, Any]]] = {}
    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        result[sheet_name] = _sheet_to_rows(ws)

    wb.close()
    return result


def validate_excel_structure(
    file_path: str,
    required_sheets: list[str] | None = None,
    required_columns: dict[str, list[str]] | None = None,
) -> tuple[bool, str | None]:
    try:
        wb = _load_workbook(file_path)
    except ValueError as exc:
        return False, str(exc)
    except FileNotFoundError as exc:
        return False, str(exc)

    existing_sheets = set(wb.sheetnames)

    if required_sheets:
        for sheet_name in required_sheets:
            if sheet_name not in existing_sheets:
                wb.close()
                return (
                    False,
                    f"Required sheet '{sheet_name}' not found. "
                    f"Available sheets: {sorted(existing_sheets)}",
                )

    if required_columns:
        for sheet_name, cols in required_columns.items():
            if sheet_name not in existing_sheets:
                wb.close()
                return (
                    False,
                    f"Sheet '{sheet_name}' (needed for column validation) not found.",
                )
            ws = wb[sheet_name]
            rows = list(ws.iter_rows(max_row=1, values_only=True))
            if not rows or all(c is None for c in rows[0]):
                wb.close()
                return (
                    False,
                    f"Sheet '{sheet_name}' has no header row; "
                    f"required columns {cols} cannot be verified.",
                )
            actual_columns = {str(c) for c in rows[0] if c is not None}
            for col in cols:
                if col not in actual_columns:
                    wb.close()
                    return (
                        False,
                        f"Required column '{col}' not found in sheet '{sheet_name}'. "
                        f"Available columns: {sorted(actual_columns)}",
                    )

    wb.close()
    return True, None

def process_uploaded_excel(
    file_path: str,
    required_sheets: list[str] | None = None,
    required_columns: dict[str, list[str]] | None = None,
) -> tuple[bool, str | None, dict[str, list[dict[str, Any]]] | None]:
    is_valid, error = validate_excel_structure(
        file_path,
        required_sheets=required_sheets,
        required_columns=required_columns,
    )
    if not is_valid:
        return False, error, None

    try:
        data = parse_excel(file_path)
    except (ValueError, FileNotFoundError) as exc:
        return False, str(exc), None

    return True, None, data