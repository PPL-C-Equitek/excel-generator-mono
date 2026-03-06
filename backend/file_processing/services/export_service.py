import csv
import io
import zipfile


class OutputLLMValidationError(Exception):
    """Raised when LLM output does not satisfy CSV validation contract."""


class OutputCSVMappingError(Exception):
    """Raised when validated LLM output cannot be mapped into CSV tabular structure."""


class OutputCSVGenerationError(Exception):
    """Raised when mapped output cannot be generated into CSV content."""


class CSVSanitizationPolicy:
    """Strategy extension point for CSV header/value sanitization."""

    def sanitize_header(self, header):
        return _sanitize_csv_value(header)

    def sanitize_value(self, value):
        return _sanitize_csv_value(value)


class CSVFileNamePolicy:
    """Strategy extension point for CSV file naming."""

    def build_filename(self, sheet_name):
        return f"{sheet_name}.csv"


_SCALAR_TYPES = (str, int, float, bool, type(None))
_ALLOWED_SOURCE_TYPES = {"Excel", "PDF"}
_REQUIRED_TOP_LEVEL_KEYS = {"document_info", "summary", "content_data"}
_CSV_FORMULA_PREFIXES = ("=", "+", "-", "@")
_DEFAULT_CSV_SANITIZATION_POLICY = CSVSanitizationPolicy()
_DEFAULT_CSV_FILENAME_POLICY = CSVFileNamePolicy()


def validate_output_llm(output_json):
    if not isinstance(output_json, dict):
        raise OutputLLMValidationError("output_json root must be an object.")

    _validate_top_level(output_json)
    _validate_document_info(output_json["document_info"])
    _validate_summary(output_json["summary"])
    _validate_content_data(output_json["content_data"])

    return output_json


def _validate_top_level(payload):
    missing_keys = [key for key in _REQUIRED_TOP_LEVEL_KEYS if key not in payload]
    if missing_keys:
        raise OutputLLMValidationError(
            f"Missing required top-level keys: {missing_keys}."
        )

    if not isinstance(payload["document_info"], dict):
        raise OutputLLMValidationError("document_info must be an object.")
    if not isinstance(payload["summary"], dict):
        raise OutputLLMValidationError("summary must be an object.")
    if not isinstance(payload["content_data"], list):
        raise OutputLLMValidationError("content_data must be a list.")


def _validate_document_info(document_info):
    required_keys = ("source_type", "filename")
    for key in required_keys:
        if key not in document_info:
            raise OutputLLMValidationError(
                f"document_info is missing required key '{key}'."
            )

    source_type = document_info["source_type"]
    if not isinstance(source_type, str) or source_type not in _ALLOWED_SOURCE_TYPES:
        raise OutputLLMValidationError("document_info.source_type must be Excel or PDF.")

    filename = document_info["filename"]
    if not isinstance(filename, str) or not filename.strip():
        raise OutputLLMValidationError(
            "document_info.filename must be a non-empty string."
        )


def _validate_summary(summary):
    for key, value in summary.items():
        if not isinstance(key, str) or not key.strip():
            raise OutputLLMValidationError("summary keys must be non-empty strings.")
        if isinstance(value, (dict, list)):
            raise OutputLLMValidationError(
                f"summary['{key}'] must be a scalar value."
            )
        if not isinstance(value, _SCALAR_TYPES):
            raise OutputLLMValidationError(
                f"summary['{key}'] has unsupported value type."
            )

def _validate_content_data(content_data):
    table_names = set()
    for table_index, table in enumerate(content_data):
        if not isinstance(table, dict):
            raise OutputLLMValidationError(
                f"content_data[{table_index}] must be an object."
            )

        for required_key in ("table_name", "headers", "rows"):
            if required_key not in table:
                raise OutputLLMValidationError(
                    f"content_data[{table_index}] is missing required key '{required_key}'."
                )

        table_name = table["table_name"]
        if not isinstance(table_name, str) or not table_name.strip():
            raise OutputLLMValidationError(
                f"content_data[{table_index}].table_name must be a non-empty string."
            )
        if table_name in table_names:
            raise OutputLLMValidationError(
                f"Duplicate table_name found: '{table_name}'."
            )
        table_names.add(table_name)

        headers = _validate_headers(table["headers"], table_index)
        _validate_rows(table["rows"], headers, table_index)


def _validate_headers(headers, table_index):
    if not isinstance(headers, list):
        raise OutputLLMValidationError(
            f"content_data[{table_index}].headers must be a list."
        )
    if not headers:
        raise OutputLLMValidationError(
            f"content_data[{table_index}].headers must not be empty."
        )

    normalized_columns = []
    seen_columns = set()
    for header in headers:
        if not isinstance(header, str):
            raise OutputLLMValidationError(
                f"content_data[{table_index}] header names must be strings."
            )
        trimmed_column = header.strip()
        if not trimmed_column:
            raise OutputLLMValidationError(
                f"content_data[{table_index}] contains blank header name."
            )

        dedupe_key = trimmed_column.lower()
        if dedupe_key in seen_columns:
            raise OutputLLMValidationError(
                f"content_data[{table_index}] headers must be unique (case-insensitive)."
            )
        seen_columns.add(dedupe_key)
        normalized_columns.append(trimmed_column)

    return normalized_columns


def _validate_rows(rows, headers, table_index):
    if not isinstance(rows, list):
        raise OutputLLMValidationError(
            f"content_data[{table_index}].rows must be a list."
        )

    header_set = set(headers)
    for row_index, row in enumerate(rows):
        _validate_row_structure(
            row=row,
            headers=headers,
            header_set=header_set,
            table_index=table_index,
            row_index=row_index,
        )
        _validate_row_values(
            row=row,
            headers=headers,
            table_index=table_index,
            row_index=row_index,
        )


def _validate_row_structure(row, headers, header_set, table_index, row_index):
    if not isinstance(row, dict):
        raise OutputLLMValidationError(
            f"content_data[{table_index}], row {row_index} must be an object."
        )

    missing_columns = [header for header in headers if header not in row]
    if missing_columns:
        raise OutputLLMValidationError(
            f"content_data[{table_index}], row {row_index} is missing required headers: {missing_columns}."
        )

    unknown_columns = [key for key in row if key not in header_set]
    if unknown_columns:
        raise OutputLLMValidationError(
            f"content_data[{table_index}], row {row_index} has unknown headers: {unknown_columns}."
        )


def _validate_row_values(row, headers, table_index, row_index):
    for header in headers:
        value = row[header]
        if isinstance(value, (dict, list)):
            raise OutputLLMValidationError(
                f"content_data[{table_index}], row {row_index}, header '{header}' has unsupported nested value."
            )
        if not isinstance(value, _SCALAR_TYPES):
            raise OutputLLMValidationError(
                f"content_data[{table_index}], row {row_index}, header '{header}' has unsupported value type."
            )


def map_output_csv(validated_output):
    if not isinstance(validated_output, dict):
        raise OutputCSVMappingError("validated_output must be an object.")

    tables = validated_output.get("content_data")
    if not isinstance(tables, list):
        raise OutputCSVMappingError("validated_output.content_data must be a list.")

    mapped_sheets = []
    for table_index, table in enumerate(tables):
        if not isinstance(table, dict):
            raise OutputCSVMappingError(
                f"content_data[{table_index}] must be an object."
            )

        for required_key in ("table_name", "headers", "rows"):
            if required_key not in table:
                raise OutputCSVMappingError(
                    f"content_data[{table_index}] is missing required key '{required_key}'."
                )

        name = table["table_name"]
        headers = table["headers"]
        rows = table["rows"]

        if not isinstance(headers, list) or not headers:
            raise OutputCSVMappingError(
                f"content_data[{table_index}].headers must be a non-empty list."
            )
        if not isinstance(rows, list):
            raise OutputCSVMappingError(
                f"content_data[{table_index}].rows must be a list."
            )

        mapped_rows = _map_rows(headers=headers, rows=rows, table_index=table_index)
        mapped_sheets.append(
            {
                "name": name,
                "headers": headers,
                "rows": mapped_rows,
            }
        )

    return {
        "document_info": validated_output.get("document_info", {}),
        "summary": validated_output.get("summary", {}),
        "sheets": mapped_sheets,
    }


def _map_rows(headers, rows, table_index):
    mapped_rows = []
    header_set = set(headers)

    for row_index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise OutputCSVMappingError(
                f"content_data[{table_index}], row {row_index} must be an object."
            )

        missing_headers = [header for header in headers if header not in row]
        if missing_headers:
            raise OutputCSVMappingError(
                f"content_data[{table_index}], row {row_index} is missing headers: {missing_headers}."
            )

        unknown_headers = [key for key in row.keys() if key not in header_set]
        if unknown_headers:
            raise OutputCSVMappingError(
                f"content_data[{table_index}], row {row_index} has unknown headers: {unknown_headers}."
            )

        mapped_rows.append([row[header] for header in headers])

    return mapped_rows


def generate_csv(mapped_output, sanitization_policy=None, filename_policy=None):
    if not isinstance(mapped_output, dict):
        raise OutputCSVGenerationError("mapped_output must be an object.")

    sheets = mapped_output.get("sheets")
    if not isinstance(sheets, list):
        raise OutputCSVGenerationError("mapped_output.sheets must be a list.")

    sanitization_policy = _resolve_sanitization_policy(sanitization_policy)
    filename_policy = _resolve_filename_policy(filename_policy)

    files = []
    for sheet_index, sheet in enumerate(sheets):
        files.append(
            _build_csv_file(
                sheet=sheet,
                sheet_index=sheet_index,
                sanitization_policy=sanitization_policy,
                filename_policy=filename_policy,
            )
        )

    return {"files": files}


def _build_csv_file(sheet, sheet_index, sanitization_policy, filename_policy):
    sheet_name, headers, rows = _validate_generate_csv_sheet(sheet, sheet_index)

    _validate_csv_headers(headers, sheet_index)
    normalized_headers = [sanitization_policy.sanitize_header(header) for header in headers]
    normalized_rows = _validate_csv_rows(
        rows=rows,
        headers=headers,
        sheet_index=sheet_index,
        sanitization_policy=sanitization_policy,
    )
    filename = filename_policy.build_filename(sheet_name)
    if not isinstance(filename, str) or not filename.strip():
        raise OutputCSVGenerationError(
            "filename_policy.build_filename must return a non-empty string."
        )

    return {
        "name": filename,
        "content": _build_csv_content(normalized_headers, normalized_rows),
    }


def _validate_generate_csv_sheet(sheet, sheet_index):
    if not isinstance(sheet, dict):
        raise OutputCSVGenerationError(f"Sheet {sheet_index} must be an object.")

    for required_key in ("name", "headers", "rows"):
        if required_key not in sheet:
            raise OutputCSVGenerationError(
                f"Sheet {sheet_index} is missing required key '{required_key}'."
            )

    sheet_name = sheet["name"]
    headers = sheet["headers"]
    rows = sheet["rows"]

    if not isinstance(sheet_name, str) or not sheet_name.strip():
        raise OutputCSVGenerationError(
            f"Sheet {sheet_index} name must be a non-empty string."
        )

    return sheet_name, headers, rows


def generate_csv_download_artifact(
    mapped_output,
    sanitization_policy=None,
    filename_policy=None,
):
    generated = generate_csv(
        mapped_output,
        sanitization_policy=sanitization_policy,
        filename_policy=filename_policy,
    )
    files = generated["files"]

    if len(files) == 1:
        single_file = files[0]
        return {
            "type": "csv",
            "name": single_file["name"],
            "content": single_file["content"].encode("utf-8"),
        }

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for file_item in files:
            archive.writestr(file_item["name"], file_item["content"])

    return {
        "type": "zip",
        "name": "csv_export.zip",
        "content": zip_buffer.getvalue(),
    }


def _validate_csv_headers(headers, sheet_index):
    if not isinstance(headers, list):
        raise OutputCSVGenerationError(f"Sheet {sheet_index} headers must be a list.")
    if not headers:
        raise OutputCSVGenerationError(
            f"Sheet {sheet_index} headers must be a non-empty list."
        )

    seen_headers = set()
    for header in headers:
        if not isinstance(header, str):
            raise OutputCSVGenerationError(
                f"Sheet {sheet_index} header names must be strings."
            )
        normalized_header = header.strip()
        if not normalized_header:
            raise OutputCSVGenerationError(
                f"Sheet {sheet_index} contains blank header name."
            )

        dedupe_key = normalized_header.lower()
        if dedupe_key in seen_headers:
            raise OutputCSVGenerationError(
                f"Sheet {sheet_index} headers must be unique (case-insensitive)."
            )
        seen_headers.add(dedupe_key)


def _validate_csv_rows(rows, headers, sheet_index, sanitization_policy):
    if not isinstance(rows, list):
        raise OutputCSVGenerationError(f"Sheet {sheet_index} rows must be a list.")

    normalized_rows = []
    for row_index, row in enumerate(rows):
        if not isinstance(row, list):
            raise OutputCSVGenerationError(
                f"Sheet {sheet_index}, row {row_index} must be a list."
            )
        if len(row) != len(headers):
            raise OutputCSVGenerationError(
                f"Sheet {sheet_index}, row {row_index} must have {len(headers)} values."
            )

        normalized_row = []
        for value in row:
            if isinstance(value, (dict, list)):
                raise OutputCSVGenerationError(
                    f"Sheet {sheet_index}, row {row_index} contains unsupported nested value."
                )
            if not isinstance(value, _SCALAR_TYPES):
                raise OutputCSVGenerationError(
                    f"Sheet {sheet_index}, row {row_index} contains unsupported value type."
                )
            normalized_row.append(sanitization_policy.sanitize_value(value))
        normalized_rows.append(normalized_row)

    return normalized_rows


def _resolve_sanitization_policy(sanitization_policy):
    return _resolve_policy_with_methods(
        policy=sanitization_policy,
        default_policy=_DEFAULT_CSV_SANITIZATION_POLICY,
        required_methods=("sanitize_header", "sanitize_value"),
        error_message=(
            "sanitization_policy must implement callable sanitize_header and "
            "sanitize_value methods."
        ),
    )


def _resolve_filename_policy(filename_policy):
    return _resolve_policy_with_methods(
        policy=filename_policy,
        default_policy=_DEFAULT_CSV_FILENAME_POLICY,
        required_methods=("build_filename",),
        error_message="filename_policy must implement callable build_filename method.",
    )


def _resolve_policy_with_methods(
    policy,
    default_policy,
    required_methods,
    error_message,
):
    if policy is None:
        return default_policy

    for method_name in required_methods:
        if not callable(getattr(policy, method_name, None)):
            raise OutputCSVGenerationError(error_message)

    return policy


def _sanitize_csv_value(value):
    if not isinstance(value, str):
        return value

    stripped_value = value.lstrip()
    if not stripped_value:
        return value

    if stripped_value.startswith("'"):
        return value

    if stripped_value[0] in _CSV_FORMULA_PREFIXES:
        return f"'{value}"

    return value


def _build_csv_content(headers, rows):
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(headers)
    writer.writerows(rows)
    return output.getvalue()
