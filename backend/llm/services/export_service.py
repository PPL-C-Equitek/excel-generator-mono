import json

def _normalize_filename_candidate(value):
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _extract_document_info_filename(payload):
    if not isinstance(payload, dict):
        return None

    document_info = payload.get("document_info")
    if not isinstance(document_info, dict):
        return None

    return _normalize_filename_candidate(document_info.get("filename"))


def extract_original_name(input_json, output_json) -> str:
    if isinstance(input_json, dict):
        input_filename = _normalize_filename_candidate(input_json.get("filename"))
        if input_filename:
            return input_filename

    return (
        _extract_document_info_filename(input_json)
        or _extract_document_info_filename(output_json)
        or "generated-output"
    )


def _extract_document_type(payload) -> str:
    if not isinstance(payload, dict):
        return "unknown"

    document_info = payload.get("document_info")
    if isinstance(document_info, dict):
        for key in ("source_type", "document_type", "file_type", "format"):
            value = document_info.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip().lower()

    for key in ("document_type", "file_type", "format"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip().lower()

    return "unknown"


def _format_export_source_type(value: str) -> str:
    normalized = value.strip().lower()
    if normalized in {"pdf"}:
        return "PDF"
    if normalized in {"excel", "xlsx", "xls"}:
        return "Excel"
    return ""


def _resolve_export_source_type(input_json, output_json) -> str:
    source_type = _format_export_source_type(_extract_document_type(input_json))
    if source_type:
        return source_type

    filename = extract_original_name(input_json, output_json).lower()
    if filename.endswith(".pdf"):
        return "PDF"

    return "Excel"


DEFAULT_EXPORT_TABLE_NAME = "Sheet1"
DEFAULT_EXPORT_VALUE_HEADER = "value"


def _get_cell_serialization_cache_key(value):
    if isinstance(value, bytes):
        return ("bytes", value)
    return ("object", id(value))


def _to_scalar_cell(value, serialization_cache=None):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value

    cache_key = None
    if serialization_cache is not None:
        cache_key = _get_cell_serialization_cache_key(value)
        cached_value = serialization_cache.get(cache_key)
        if cached_value is not None:
            return cached_value

    try:
        serialized_value = str(value) if isinstance(value, bytes) else json.dumps(value)
    except Exception:
        serialized_value = "[Unserializable Value]"

    if serialization_cache is not None and cache_key is not None:
        serialization_cache[cache_key] = serialized_value

    return serialized_value


def _normalize_headers(raw_headers):
    if not raw_headers:
        return [DEFAULT_EXPORT_VALUE_HEADER]

    counts = {}
    normalized = []
    for index, raw_header in enumerate(raw_headers):
        trimmed = (
            raw_header.strip()
            if isinstance(raw_header, str) and raw_header.strip()
            else f"column_{index + 1}"
        )
        key = trimmed.lower()
        count = counts.get(key, 0)
        counts[key] = count + 1
        normalized.append(trimmed if count == 0 else f"{trimmed}_{count + 1}")
    return normalized


def _map_array_row_to_object(row, headers, serialization_cache=None):
    return {
        header: _to_scalar_cell(
            row[index] if index < len(row) else None,
            serialization_cache=serialization_cache,
        )
        for index, header in enumerate(headers)
    }


def _map_object_row_to_object(row, headers, serialization_cache=None):
    return {
        header: _to_scalar_cell(row.get(header), serialization_cache=serialization_cache)
        for header in headers
    }


def _map_unknown_row_to_object(row, headers, serialization_cache=None):
    mapped_row = {}
    for index, header in enumerate(headers):
        mapped_row[header] = (
            _to_scalar_cell(row, serialization_cache=serialization_cache)
            if index == 0
            else None
        )
    return mapped_row


def _collect_rows_array_metadata(rows):
    all_lists = bool(rows)
    all_dicts = bool(rows)
    max_columns = 0
    collected_headers = []
    seen_headers = set()

    for row in rows:
        is_list_row = isinstance(row, list)
        is_dict_row = isinstance(row, dict)
        all_lists = all_lists and is_list_row
        all_dicts = all_dicts and is_dict_row

        if is_list_row:
            max_columns = max(max_columns, len(row))
        if is_dict_row:
            for key in row:
                if key not in seen_headers:
                    seen_headers.add(key)
                    collected_headers.append(key)

    return all_lists, all_dicts, max_columns, collected_headers


def _build_rows_from_generated_output_rows(rows, headers, serialization_cache=None):
    normalized_rows = []
    for row in rows:
        if isinstance(row, list):
            normalized_rows.append(
                _map_array_row_to_object(
                    row,
                    headers,
                    serialization_cache=serialization_cache,
                )
            )
        elif isinstance(row, dict):
            normalized_rows.append(
                _map_object_row_to_object(
                    row,
                    headers,
                    serialization_cache=serialization_cache,
                )
            )
        else:
            normalized_rows.append(
                _map_unknown_row_to_object(
                    row,
                    headers,
                    serialization_cache=serialization_cache,
                )
            )
    return normalized_rows


def _infer_headers_and_rows_from_rows_array(rows, serialization_cache=None):
    all_lists, all_dicts, max_columns, collected_headers = _collect_rows_array_metadata(rows)

    if all_lists:
        headers = _normalize_headers(
            [f"column_{index + 1}" for index in range(max_columns)]
        )
        return headers, _build_rows_from_generated_output_rows(
            rows,
            headers,
            serialization_cache=serialization_cache,
        )

    if all_dicts:
        headers = _normalize_headers(collected_headers)
        return headers, _build_rows_from_generated_output_rows(
            rows,
            headers,
            serialization_cache=serialization_cache,
        )

    headers = [DEFAULT_EXPORT_VALUE_HEADER]
    normalized_rows = [
        {
            DEFAULT_EXPORT_VALUE_HEADER: _to_scalar_cell(
                value,
                serialization_cache=serialization_cache,
            )
        }
        for value in rows
    ]
    return headers, normalized_rows


def _infer_headers_and_rows_from_output(output_json, serialization_cache=None):
    if isinstance(output_json, dict):
        headers = _normalize_headers(list(output_json.keys()))
        return headers, [
            _map_object_row_to_object(
                output_json,
                headers,
                serialization_cache=serialization_cache,
            )
        ]

    if isinstance(output_json, list):
        return _infer_headers_and_rows_from_rows_array(
            output_json,
            serialization_cache=serialization_cache,
        )

    return [DEFAULT_EXPORT_VALUE_HEADER], [
        {
            DEFAULT_EXPORT_VALUE_HEADER: _to_scalar_cell(
                output_json,
                serialization_cache=serialization_cache,
            )
        }
    ]


def _build_sheet_content_data(entries, serialization_cache):
    content_data = []
    for index, (sheet_name, value) in enumerate(entries):
        headers, rows = _infer_headers_and_rows_from_rows_array(
            value,
            serialization_cache=serialization_cache,
        )
        normalized_name = sheet_name.strip() if isinstance(sheet_name, str) else ""
        table_name = normalized_name or f"Sheet{index + 1}"
        content_data.append({"table_name": table_name, "headers": headers, "rows": rows})
    return content_data


def _build_content_data_from_output(output_json, serialization_cache=None):
    if isinstance(output_json, dict):
        raw_content_data = output_json.get("content_data")
        if isinstance(raw_content_data, list) and raw_content_data:
            return raw_content_data

        direct_headers = output_json.get("headers")
        direct_rows = output_json.get("rows")
        if isinstance(direct_headers, list) and isinstance(direct_rows, list):
            headers = _normalize_headers(direct_headers)
            return [
                {
                    "table_name": DEFAULT_EXPORT_TABLE_NAME,
                    "headers": headers,
                    "rows": _build_rows_from_generated_output_rows(
                        direct_rows,
                        headers,
                        serialization_cache=serialization_cache,
                    ),
                }
            ]

        entries = list(output_json.items())
        if entries and all(isinstance(value, list) for _, value in entries):
            return _build_sheet_content_data(entries, serialization_cache)

    headers, rows = _infer_headers_and_rows_from_output(
        output_json,
        serialization_cache=serialization_cache,
    )
    return [
        {
            "table_name": DEFAULT_EXPORT_TABLE_NAME,
            "headers": headers,
            "rows": rows,
        }
    ]


def build_export_output_json(input_json, output_json):
    serialization_cache = {}
    content_data = _build_content_data_from_output(
        output_json,
        serialization_cache=serialization_cache,
    )

    total_rows = sum(len(table["rows"]) for table in content_data)
    total_columns = max((len(table["headers"]) for table in content_data), default=0)

    return {
        "document_info": {
            "source_type": _resolve_export_source_type(input_json, output_json),
            "filename": extract_original_name(input_json, output_json),
        },
        "summary": {
            "total_tables": len(content_data),
            "total_rows": total_rows,
            "total_columns": total_columns,
        },
        "content_data": content_data,
    }

