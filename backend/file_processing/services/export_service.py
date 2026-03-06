import csv
import io


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
_ALLOWED_STATUS = {"ok", "error"}
_ALLOWED_VALIDATION_LEVELS = {"info", "warning", "error"}
_REQUIRED_TOP_LEVEL_KEYS = {"status", "summary", "sheets", "validations", "errors"}
_CSV_FORMULA_PREFIXES = ("=", "+", "-", "@")
_DEFAULT_CSV_SANITIZATION_POLICY = CSVSanitizationPolicy()
_DEFAULT_CSV_FILENAME_POLICY = CSVFileNamePolicy()


def validate_output_llm(output_json):
    if not isinstance(output_json, dict):
        raise OutputLLMValidationError("output_json root must be an object.")

    _validate_top_level(output_json)
    sheet_names = _validate_sheets(output_json["sheets"])
    _validate_validations(output_json["validations"], sheet_names)
    _validate_errors(output_json["errors"])

    return output_json


def _validate_top_level(payload):
    missing_keys = [key for key in _REQUIRED_TOP_LEVEL_KEYS if key not in payload]
    if missing_keys:
        raise OutputLLMValidationError(
            f"Missing required top-level keys: {missing_keys}."
        )

    status = payload["status"]
    if not isinstance(status, str) or status not in _ALLOWED_STATUS:
        raise OutputLLMValidationError("status must be one of: ok, error.")

    summary = payload["summary"]
    if not isinstance(summary, str):
        raise OutputLLMValidationError("summary must be a string.")

    if not isinstance(payload["sheets"], list):
        raise OutputLLMValidationError("sheets must be a list.")
    if not isinstance(payload["validations"], list):
        raise OutputLLMValidationError("validations must be a list.")
    if not isinstance(payload["errors"], list):
        raise OutputLLMValidationError("errors must be a list.")


def _validate_sheets(sheets):
    sheet_names = set()
    for sheet_index, sheet in enumerate(sheets):
        if not isinstance(sheet, dict):
            raise OutputLLMValidationError(f"Sheet {sheet_index} must be an object.")

        for required_key in ("name", "columns", "rows"):
            if required_key not in sheet:
                raise OutputLLMValidationError(
                    f"Sheet {sheet_index} is missing required key '{required_key}'."
                )

        sheet_name = sheet["name"]
        if not isinstance(sheet_name, str) or not sheet_name.strip():
            raise OutputLLMValidationError(
                f"Sheet {sheet_index} name must be a non-empty string."
            )
        if sheet_name in sheet_names:
            raise OutputLLMValidationError(
                f"Duplicate sheet name found: '{sheet_name}'."
            )
        sheet_names.add(sheet_name)

        columns = _validate_columns(sheet["columns"], sheet_index)
        _validate_rows(sheet["rows"], columns, sheet_index)

    return sheet_names


def _validate_columns(columns, sheet_index):
    if not isinstance(columns, list):
        raise OutputLLMValidationError(f"Sheet {sheet_index} columns must be a list.")
    if not columns:
        raise OutputLLMValidationError(f"Sheet {sheet_index} columns must not be empty.")

    normalized_columns = []
    seen_columns = set()
    for column in columns:
        if not isinstance(column, str):
            raise OutputLLMValidationError(
                f"Sheet {sheet_index} column names must be strings."
            )
        trimmed_column = column.strip()
        if not trimmed_column:
            raise OutputLLMValidationError(
                f"Sheet {sheet_index} contains blank column name."
            )

        dedupe_key = trimmed_column.lower()
        if dedupe_key in seen_columns:
            raise OutputLLMValidationError(
                f"Sheet {sheet_index} columns must be unique (case-insensitive)."
            )
        seen_columns.add(dedupe_key)
        normalized_columns.append(trimmed_column)

    return normalized_columns


def _validate_rows(rows, columns, sheet_index):
    if not isinstance(rows, list):
        raise OutputLLMValidationError(f"Sheet {sheet_index} rows must be a list.")

    column_set = set(columns)
    for row_index, row in enumerate(rows):
        _validate_row_structure(
            row=row,
            columns=columns,
            column_set=column_set,
            sheet_index=sheet_index,
            row_index=row_index,
        )
        _validate_row_values(
            row=row,
            columns=columns,
            sheet_index=sheet_index,
            row_index=row_index,
        )


def _validate_row_structure(row, columns, column_set, sheet_index, row_index):
    if not isinstance(row, dict):
        raise OutputLLMValidationError(
            f"Sheet {sheet_index}, row {row_index} must be an object."
        )

    missing_columns = [column for column in columns if column not in row]
    if missing_columns:
        raise OutputLLMValidationError(
            f"Sheet {sheet_index}, row {row_index} is missing required columns: {missing_columns}."
        )

    unknown_columns = [key for key in row if key not in column_set]
    if unknown_columns:
        raise OutputLLMValidationError(
            f"Sheet {sheet_index}, row {row_index} has unknown columns: {unknown_columns}."
        )


def _validate_row_values(row, columns, sheet_index, row_index):
    for column in columns:
        value = row[column]
        if isinstance(value, (dict, list)):
            raise OutputLLMValidationError(
                f"Sheet {sheet_index}, row {row_index}, column '{column}' has unsupported nested value."
            )
        if not isinstance(value, _SCALAR_TYPES):
            raise OutputLLMValidationError(
                f"Sheet {sheet_index}, row {row_index}, column '{column}' has unsupported value type."
            )


def _validate_validations(validations, sheet_names):
    for index, validation in enumerate(validations):
        _validate_validation_item_structure(validation, index)
        _validate_validation_item_fields(validation, sheet_names, index)


def _validate_validation_item_structure(validation, index):
    if not isinstance(validation, dict):
        raise OutputLLMValidationError(
            f"Validation item {index} must be an object."
        )

    for required_key in ("sheet", "rule", "level"):
        if required_key not in validation:
            raise OutputLLMValidationError(
                f"Validation item {index} is missing required key '{required_key}'."
            )


def _validate_validation_item_fields(validation, sheet_names, index):
    sheet_name = validation["sheet"]
    rule = validation["rule"]
    level = validation["level"]

    if not isinstance(sheet_name, str) or not sheet_name.strip():
        raise OutputLLMValidationError(
            f"Validation item {index} sheet must be a non-empty string."
        )
    if sheet_name not in sheet_names:
        raise OutputLLMValidationError(
            f"Validation item {index} references unknown sheet '{sheet_name}'."
        )

    if not isinstance(rule, str) or not rule.strip():
        raise OutputLLMValidationError(
            f"Validation item {index} rule must be a non-empty string."
        )

    if not isinstance(level, str) or level not in _ALLOWED_VALIDATION_LEVELS:
        raise OutputLLMValidationError(
            f"Validation item {index} level must be one of: info, warning, error."
        )


def _validate_errors(errors):
    for index, error in enumerate(errors):
        if not isinstance(error, str):
            raise OutputLLMValidationError(
                f"errors[{index}] must be a string."
            )


def map_output_csv(validated_output):
    if not isinstance(validated_output, dict):
        raise OutputCSVMappingError("validated_output must be an object.")

    sheets = validated_output.get("sheets")
    if not isinstance(sheets, list):
        raise OutputCSVMappingError("validated_output.sheets must be a list.")

    mapped_sheets = []
    for sheet_index, sheet in enumerate(sheets):
        if not isinstance(sheet, dict):
            raise OutputCSVMappingError(f"Sheet {sheet_index} must be an object.")

        for required_key in ("name", "columns", "rows"):
            if required_key not in sheet:
                raise OutputCSVMappingError(
                    f"Sheet {sheet_index} is missing required key '{required_key}'."
                )

        name = sheet["name"]
        headers = sheet["columns"]
        rows = sheet["rows"]

        if not isinstance(headers, list) or not headers:
            raise OutputCSVMappingError(
                f"Sheet {sheet_index} columns must be a non-empty list."
            )
        if not isinstance(rows, list):
            raise OutputCSVMappingError(f"Sheet {sheet_index} rows must be a list.")

        mapped_rows = _map_rows(headers=headers, rows=rows, sheet_index=sheet_index)
        mapped_sheets.append(
            {
                "name": name,
                "headers": headers,
                "rows": mapped_rows,
            }
        )

    return {"sheets": mapped_sheets}


def _map_rows(headers, rows, sheet_index):
    mapped_rows = []
    header_set = set(headers)

    for row_index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise OutputCSVMappingError(
                f"Sheet {sheet_index}, row {row_index} must be an object."
            )

        missing_headers = [header for header in headers if header not in row]
        if missing_headers:
            raise OutputCSVMappingError(
                f"Sheet {sheet_index}, row {row_index} is missing headers: {missing_headers}."
            )

        unknown_headers = [key for key in row.keys() if key not in header_set]
        if unknown_headers:
            raise OutputCSVMappingError(
                f"Sheet {sheet_index}, row {row_index} has unknown headers: {unknown_headers}."
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

        _validate_csv_headers(headers, sheet_index)
        normalized_headers = [
            sanitization_policy.sanitize_header(header) for header in headers
        ]
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

        files.append(
            {
                "name": filename,
                "content": _build_csv_content(normalized_headers, normalized_rows),
            }
        )

    return {"files": files}


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
