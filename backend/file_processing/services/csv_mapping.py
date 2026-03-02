class OutputCSVMappingError(Exception):
    """Raised when validated LLM output cannot be mapped into CSV tabular structure."""


class MappingOutputCSVService:
    def map_output_csv(self, validated_output):
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

            mapped_rows = self._map_rows(headers=headers, rows=rows, sheet_index=sheet_index)
            mapped_sheets.append(
                {
                    "name": name,
                    "headers": headers,
                    "rows": mapped_rows,
                }
            )

        return {"sheets": mapped_sheets}

    def _map_rows(self, headers, rows, sheet_index):
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