class OutputLLMValidationError(Exception):
    """Raised when LLM output does not satisfy CSV validation contract."""


class ValidateOutputLLMService:
    _SCALAR_TYPES = (str, int, float, bool, type(None))
    _ALLOWED_STATUS = {"ok", "error"}
    _ALLOWED_VALIDATION_LEVELS = {"info", "warning", "error"}
    _REQUIRED_TOP_LEVEL_KEYS = {"status", "summary", "sheets", "validations", "errors"}

    def validate_output_llm(self, output_json):
        if not isinstance(output_json, dict):
            raise OutputLLMValidationError("output_json root must be an object.")

        self._validate_top_level(output_json)
        sheet_names = self._validate_sheets(output_json["sheets"])
        self._validate_validations(output_json["validations"], sheet_names)
        self._validate_errors(output_json["errors"])

        return output_json

    def _validate_top_level(self, payload):
        missing_keys = [key for key in self._REQUIRED_TOP_LEVEL_KEYS if key not in payload]
        if missing_keys:
            raise OutputLLMValidationError(
                f"Missing required top-level keys: {missing_keys}."
            )

        status = payload["status"]
        if not isinstance(status, str) or status not in self._ALLOWED_STATUS:
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

    def _validate_sheets(self, sheets):
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

            columns = self._validate_columns(sheet["columns"], sheet_index)
            self._validate_rows(sheet["rows"], columns, sheet_index)

        return sheet_names

    def _validate_columns(self, columns, sheet_index):
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

    def _validate_rows(self, rows, columns, sheet_index):
        if not isinstance(rows, list):
            raise OutputLLMValidationError(f"Sheet {sheet_index} rows must be a list.")

        column_set = set(columns)
        for row_index, row in enumerate(rows):
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

            for column in columns:
                value = row[column]
                if isinstance(value, (dict, list)):
                    raise OutputLLMValidationError(
                        f"Sheet {sheet_index}, row {row_index}, column '{column}' has unsupported nested value."
                    )
                if not isinstance(value, self._SCALAR_TYPES):
                    raise OutputLLMValidationError(
                        f"Sheet {sheet_index}, row {row_index}, column '{column}' has unsupported value type."
                    )

    def _validate_validations(self, validations, sheet_names):
        for index, validation in enumerate(validations):
            if not isinstance(validation, dict):
                raise OutputLLMValidationError(
                    f"Validation item {index} must be an object."
                )

            for required_key in ("sheet", "rule", "level"):
                if required_key not in validation:
                    raise OutputLLMValidationError(
                        f"Validation item {index} is missing required key '{required_key}'."
                    )

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

            if not isinstance(level, str) or level not in self._ALLOWED_VALIDATION_LEVELS:
                raise OutputLLMValidationError(
                    f"Validation item {index} level must be one of: info, warning, error."
                )

    def _validate_errors(self, errors):
        for index, error in enumerate(errors):
            if not isinstance(error, str):
                raise OutputLLMValidationError(
                    f"errors[{index}] must be a string."
                )