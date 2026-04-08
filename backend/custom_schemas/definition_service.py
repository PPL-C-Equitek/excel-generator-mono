from django.core.exceptions import ValidationError

from .constants import DEFAULT_OUTPUT_TABLE_NAME


class CustomSchemaDefinitionService:
    def validate_schema_definition(self, definition):
        if not isinstance(definition, dict):
            raise ValidationError({"definition": ["Definition must be a JSON object."]})

        columns = self._get_columns(definition)
        errors = self._validate_columns(columns)

        if errors:
            raise ValidationError({"definition": errors})

        return definition

    def _get_columns(self, definition):
        columns = definition.get("columns")
        if isinstance(columns, list) and columns:
            return columns

        raise ValidationError(
            {"definition": ["Definition must include a non-empty 'columns' list."]}
        )

    def _validate_columns(self, columns):
        errors = []
        seen_column_names = set()

        for column_index, column in enumerate(columns):
            errors.extend(
                self._validate_column(column_index, column, seen_column_names)
            )

        return errors

    def _validate_column(self, column_index, column, seen_column_names):
        if not isinstance(column, dict):
            return [f"columns[{column_index}] must be an object."]

        errors = []
        self._validate_column_name(
            column_index,
            column.get("name"),
            seen_column_names,
            errors,
        )
        self._validate_description(column_index, column.get("description"), errors)
        return errors

    def _validate_column_name(
        self,
        column_index,
        column_name,
        seen_column_names,
        errors,
    ):
        if not isinstance(column_name, str) or not column_name.strip():
            errors.append(f"columns[{column_index}].name must be a non-empty string.")
            return

        normalized_column_name = column_name.strip().lower()
        if normalized_column_name in seen_column_names:
            errors.append("columns must not contain duplicate names.")
            return

        seen_column_names.add(normalized_column_name)

    def _validate_description(self, column_index, description, errors):
        if description is None:
            errors.append(f"columns[{column_index}].description is required.")
            return

        if not isinstance(description, str):
            errors.append(f"columns[{column_index}].description must be a string.")

    def build_prompt_fragment(self, definition):
        self.validate_schema_definition(definition)

        lines = [
            "Apply the following custom output schema.",
            "Keep the top-level JSON keys exactly as: document_info, summary, content_data.",
            f'Use a single content_data table named "{DEFAULT_OUTPUT_TABLE_NAME}".',
            "Use the following headers exactly and keep each row object limited to these headers.",
            "Custom schema columns:",
        ]

        for column in definition["columns"]:
            description = column["description"].strip()
            detail = f'  - {column["name"]}'
            if description:
                detail += f": {description}"
            lines.append(detail)

        return "\n".join(lines)


def validate_schema_definition(definition):
    return CustomSchemaDefinitionService().validate_schema_definition(definition)


def build_schema_prompt_fragment(definition):
    return CustomSchemaDefinitionService().build_prompt_fragment(definition)
