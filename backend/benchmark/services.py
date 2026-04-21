import csv
import json
from datetime import date
from pathlib import Path

from django.core.exceptions import ValidationError


class DatasetValidationError(ValidationError):
    def __init__(self, message="Format Dataset Tidak Valid"):
        super().__init__(message)


class DatasetLoader:
    allowed_extensions = {".csv", ".json"}

    def load(self, dataset_path, schema):
        return self.load_and_validate(dataset_path, schema)

    def load_and_validate(self, dataset_path, schema):
        path = Path(dataset_path)
        extension = path.suffix.lower()

        if extension not in self.allowed_extensions:
            raise DatasetValidationError()

        columns, mandatory_columns = self._validate_schema(schema)

        if extension == ".csv":
            return self._parse_csv(path, columns, mandatory_columns)

        return self._parse_json(path, columns, mandatory_columns)

    def _parse_csv(self, dataset_path, columns, mandatory_columns):
        try:
            with dataset_path.open("r", encoding="utf-8-sig", newline="") as csv_file:
                reader = csv.DictReader(csv_file)
                fieldnames = set(reader.fieldnames or [])

                if not mandatory_columns.issubset(fieldnames):
                    raise DatasetValidationError()

                parsed_rows = []
                for row in reader:
                    if self._is_empty_mapping(row):
                        continue

                    try:
                        parsed_rows.append(self._parse_row(row, columns))
                    except (TypeError, ValueError, DatasetValidationError):
                        continue

                return parsed_rows
        except DatasetValidationError:
            raise
        except (csv.Error, UnicodeDecodeError, OSError, Exception) as exc:
            raise DatasetValidationError() from exc

    def _parse_json(self, dataset_path, columns, mandatory_columns):
        try:
            with dataset_path.open("r", encoding="utf-8") as json_file:
                payload = json.load(json_file)

            if not isinstance(payload, list):
                raise DatasetValidationError()

            fieldnames = set()
            for item in payload:
                if isinstance(item, dict):
                    fieldnames.update(item.keys())

            if not mandatory_columns.issubset(fieldnames):
                raise DatasetValidationError()

            parsed_rows = []
            for row in payload:
                if self._is_empty_mapping(row):
                    continue

                try:
                    parsed_rows.append(self._parse_row(row, columns))
                except (TypeError, ValueError, DatasetValidationError):
                    continue

            return parsed_rows
        except DatasetValidationError:
            raise
        except (json.JSONDecodeError, UnicodeDecodeError, OSError, Exception) as exc:
            raise DatasetValidationError() from exc

    def _validate_schema(self, schema):
        if not isinstance(schema, dict):
            raise DatasetValidationError()

        columns = schema.get("columns")
        if not isinstance(columns, list):
            raise DatasetValidationError()

        validated_columns = []
        mandatory_columns = set()
        for column in columns:
            if not isinstance(column, dict):
                raise DatasetValidationError()

            name = column.get("name")
            if not isinstance(name, str) or not name.strip():
                raise DatasetValidationError()

            normalized_column = {
                "name": name.strip(),
                "type": column.get("type"),
                "format": column.get("format"),
                "required": bool(column.get("required")),
            }
            validated_columns.append(normalized_column)

            if normalized_column["required"]:
                mandatory_columns.add(normalized_column["name"])

        return validated_columns, mandatory_columns

    def _parse_row(self, row, columns):
        if not isinstance(row, dict):
            raise DatasetValidationError()

        parsed = {}
        for column in columns:
            name = column["name"]
            raw_value = row.get(name)

            if self._is_empty_value(raw_value):
                if column.get("required"):
                    raise DatasetValidationError()
                parsed[name] = None
                continue

            parsed[name] = self._coerce_value(raw_value, column)

        return parsed

    def _coerce_value(self, value, column):
        value_type = column.get("type")

        if value_type == "integer":
            return int(value)

        if value_type == "string":
            text = value.strip() if isinstance(value, str) else str(value)
            if column.get("format") == "date":
                date.fromisoformat(text)
            return text

        return value

    def _is_empty_mapping(self, row):
        return not isinstance(row, dict) or all(
            self._is_empty_value(value) for value in row.values()
        )

    def _is_empty_value(self, value):
        if value is None:
            return True
        if isinstance(value, str):
            return value.strip() == ""
        return False
