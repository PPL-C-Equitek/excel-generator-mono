from __future__ import annotations

import os
from typing import Any, IO
import logging

from openpyxl.utils.exceptions import InvalidFileException
from zipfile import BadZipFile

logger = logging.getLogger(__name__)

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
        return load_workbook(file_or_path, read_only=True, data_only=True)
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

def _load_xls_workbook(file_path: str):
    try:
        import xlrd
    except ImportError as exc:
        raise RuntimeError(
            "xlrd tidak terinstall. Jalankan: pip install xlrd"
        ) from exc

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File tidak ditemukan: {file_path}")

    try:
        return xlrd.open_workbook(file_path)
    except Exception as exc:
        raise ValueError(
            f"File Excel (.xls) corrupted atau cannot read: {exc}"
        ) from exc


def _xls_sheet_to_rows(sheet) -> list[list[Any]]:
    data_rows: list[list[Any]] = []

    for row_idx in range(sheet.nrows):

        row_list = [
            sheet.cell_value(row_idx, col_idx)
            for col_idx in range(sheet.ncols)
        ]

        # normalize values
        for i, val in enumerate(row_list):
            if isinstance(val, float) and val == int(val):
                row_list[i] = str(int(val))
            elif val == "":
                row_list[i] = None

        null_count = 0
        while row_list and (row_list[-1] is None or row_list[-1] == ""):
            row_list.pop()
            null_count += 1

        if not row_list and null_count == sheet.ncols:
            continue

        if null_count > 1:
            row_list.append(f"nullx{null_count}")
        elif null_count == 1:
            row_list.append("null")

        data_rows.append(row_list)

    return data_rows


def parse_xls(file_path: str) -> dict[str, list[list[Any]]]:

    wb = _load_xls_workbook(file_path)

    result: dict[str, list[list[Any]]] = {}

    for sheet_name in wb.sheet_names():
        ws = wb.sheet_by_name(sheet_name)
        result[sheet_name] = _xls_sheet_to_rows(ws)

    return result

def process_uploaded_excel(
    file_or_path: str | IO[bytes] | Any,
) -> tuple[bool, str | None, dict[str, list[list[Any]]] | None]:

    try:

        ext = ""
        if isinstance(file_or_path, str):
            ext = os.path.splitext(file_or_path)[1].lower()

        if ext == ".xls":
            data = parse_xls(file_or_path)
        else:
            data = parse_excel(file_or_path)

    except FileNotFoundError as exc:
        return False, str(exc), None

    except Exception:
        logger.exception("Excel parsing failed")
        return False, "Invalid or corrupted Excel file.", None

    return True, None, data