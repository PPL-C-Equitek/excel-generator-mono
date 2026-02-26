class OutputLLMValidationError(Exception):
    """Raised when LLM output does not satisfy CSV validation contract."""


class ValidateOutputLLMService:
    _SCALAR_TYPES = (str, int, float, bool, type(None))

    def validate_output_llm(self, output_json):
        if isinstance(output_json, dict):
            return self._validate_object_schema(output_json)
        if isinstance(output_json, list):
            return self._validate_array_schema(output_json)
        raise OutputLLMValidationError("output_json root must be an object or array.")

    def _validate_object_schema(self, payload):
        allowed_keys = {"headers", "rows"}
        unknown_keys = [key for key in payload.keys() if key not in allowed_keys]
        if unknown_keys:
            raise OutputLLMValidationError(
                f"Unknown top-level keys in output_json: {unknown_keys}."
            )

        if "headers" not in payload:
            raise OutputLLMValidationError("headers is required.")
        if "rows" not in payload:
            raise OutputLLMValidationError("rows is required.")

        headers = self._validate_headers(payload["headers"])
        rows = self._validate_rows(payload["rows"], headers)
        return {"headers": headers, "rows": rows}

    def _validate_array_schema(self, payload):
        if not payload:
            raise OutputLLMValidationError(
                "Cannot infer headers from empty output_json array."
            )

        first_row = payload[0]
        if not isinstance(first_row, dict):
            raise OutputLLMValidationError("Each row must be an object.")

        headers = self._validate_headers(list(first_row.keys()))
        rows = self._validate_rows(payload, headers)
        return {"headers": headers, "rows": rows}

    def _validate_headers(self, headers):
        if not isinstance(headers, list):
            raise OutputLLMValidationError("headers must be a list.")
        if not headers:
            raise OutputLLMValidationError("headers must not be empty.")

        normalized_headers = []
        seen = set()

        for header in headers:
            if not isinstance(header, str):
                raise OutputLLMValidationError("Each header must be a string.")

            trimmed_header = header.strip()
            if not trimmed_header:
                raise OutputLLMValidationError("Header must not be blank.")

            dedupe_key = trimmed_header.lower()
            if dedupe_key in seen:
                raise OutputLLMValidationError(
                    "Headers must be unique (case-insensitive)."
                )
            seen.add(dedupe_key)
            normalized_headers.append(trimmed_header)

        return normalized_headers

    def _validate_rows(self, rows, headers):
        if not isinstance(rows, list):
            raise OutputLLMValidationError("rows must be a list.")

        validated_rows = []
        header_set = set(headers)

        for index, row in enumerate(rows):
            if not isinstance(row, dict):
                raise OutputLLMValidationError(f"Row {index} must be an object.")

            row_keys = set(row.keys())
            missing_headers = [header for header in headers if header not in row]
            if missing_headers:
                raise OutputLLMValidationError(
                    f"Row {index} is missing required headers: {missing_headers}."
                )

            extra_headers = [key for key in row.keys() if key not in header_set]
            if extra_headers:
                raise OutputLLMValidationError(
                    f"Row {index} has unknown headers: {extra_headers}."
                )

            normalized_row = {}
            for header in headers:
                value = row[header]
                if isinstance(value, (dict, list)):
                    raise OutputLLMValidationError(
                        f"Row {index}, header '{header}' has unsupported nested value."
                    )
                if not isinstance(value, self._SCALAR_TYPES):
                    raise OutputLLMValidationError(
                        f"Row {index}, header '{header}' has unsupported value type."
                    )
                normalized_row[header] = value

            validated_rows.append(normalized_row)

        return validated_rows
