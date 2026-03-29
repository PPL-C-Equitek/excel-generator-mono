from django.core.exceptions import ValidationError


ALLOWED_COLUMN_TYPES = {
    "boolean",
    "date",
    "datetime",
    "integer",
    "number",
    "string",
}


def validate_schema_definition(definition):
    errors = []

    if not isinstance(definition, dict):
        raise ValidationError({"definition": ["Definition must be a JSON object."]})

    tables = definition.get("tables")
    if not isinstance(tables, list) or not tables:
        raise ValidationError(
            {"definition": ["Definition must include a non-empty 'tables' list."]}
        )

    seen_table_names = set()
    for table_index, table in enumerate(tables):
        if not isinstance(table, dict):
            errors.append(f"tables[{table_index}] must be an object.")
            continue

        table_name = table.get("table_name")
        if not isinstance(table_name, str) or not table_name.strip():
            errors.append(f"tables[{table_index}].table_name must be a non-empty string.")
        else:
            normalized_table_name = table_name.strip().lower()
            if normalized_table_name in seen_table_names:
                errors.append(
                    f"tables[{table_index}].table_name must be unique (case-insensitive)."
                )
            seen_table_names.add(normalized_table_name)

        columns = table.get("columns")
        if not isinstance(columns, list) or not columns:
            errors.append(f"tables[{table_index}].columns must be a non-empty list.")
            continue

        seen_column_names = set()
        for column_index, column in enumerate(columns):
            if not isinstance(column, dict):
                errors.append(
                    f"tables[{table_index}].columns[{column_index}] must be an object."
                )
                continue

            column_name = column.get("name")
            if not isinstance(column_name, str) or not column_name.strip():
                errors.append(
                    f"tables[{table_index}].columns[{column_index}].name must be a non-empty string."
                )
            else:
                normalized_column_name = column_name.strip().lower()
                if normalized_column_name in seen_column_names:
                    errors.append(
                        f"tables[{table_index}] contains duplicate column names."
                    )
                seen_column_names.add(normalized_column_name)

            column_type = column.get("type")
            if (
                not isinstance(column_type, str)
                or column_type.strip().lower() not in ALLOWED_COLUMN_TYPES
            ):
                allowed_types = ", ".join(sorted(ALLOWED_COLUMN_TYPES))
                errors.append(
                    f"tables[{table_index}].columns[{column_index}].type must be one of: {allowed_types}."
                )

            required = column.get("required")
            if not isinstance(required, bool):
                errors.append(
                    f"tables[{table_index}].columns[{column_index}].required must be a boolean."
                )

            description = column.get("description", "")
            if not isinstance(description, str):
                errors.append(
                    f"tables[{table_index}].columns[{column_index}].description must be a string."
                )

    if errors:
        raise ValidationError({"definition": errors})

    return definition


def build_schema_prompt_fragment(definition):
    validate_schema_definition(definition)

    lines = [
        "Apply the following custom output schema.",
        "Keep the top-level JSON keys exactly as: document_info, summary, content_data.",
        "For each table in content_data, use the table_name and headers exactly as defined below.",
        "Each row object must contain exactly the listed headers.",
        "Custom schema:",
    ]

    for table in definition["tables"]:
        lines.append(f'- table "{table["table_name"]}":')
        for column in table["columns"]:
            requirement = "required" if column["required"] else "optional"
            description = column.get("description", "").strip()
            detail = f'  - {column["name"]} ({column["type"]}, {requirement})'
            if description:
                detail += f": {description}"
            lines.append(detail)

    return "\n".join(lines)
