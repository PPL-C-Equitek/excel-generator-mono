from django.core.exceptions import ValidationError
from typing import Protocol


DEFAULT_OUTPUT_TABLE_NAME = "result"
MAX_CUSTOM_SCHEMAS_PER_USER = 5
ACTIVE_TRUE_VALUES = frozenset({"true", "1", "yes"})
ACTIVE_FALSE_VALUES = frozenset({"false", "0", "no"})
CUSTOM_SCHEMA_DUPLICATE_NAME_ERROR_MESSAGE = (
    "You already have a custom schema with this name."
)
CUSTOM_SCHEMA_LIMIT_EXCEEDED_ERROR_TEMPLATE = (
    "A user can only have up to {max_count} custom schemas."
)


def validate_schema_definition(definition):
    errors = []

    if not isinstance(definition, dict):
        raise ValidationError({"definition": ["Definition must be a JSON object."]})

    columns = definition.get("columns")
    if not isinstance(columns, list) or not columns:
        raise ValidationError(
            {"definition": ["Definition must include a non-empty 'columns' list."]}
        )

    seen_column_names = set()
    for column_index, column in enumerate(columns):
        if not isinstance(column, dict):
            errors.append(f"columns[{column_index}] must be an object.")
            continue

        column_name = column.get("name")
        if not isinstance(column_name, str) or not column_name.strip():
            errors.append(f"columns[{column_index}].name must be a non-empty string.")
        else:
            normalized_column_name = column_name.strip().lower()
            if normalized_column_name in seen_column_names:
                errors.append("columns must not contain duplicate names.")
            seen_column_names.add(normalized_column_name)

        description = column.get("description")
        if description is None:
            errors.append(f"columns[{column_index}].description is required.")
        elif not isinstance(description, str):
            errors.append(f"columns[{column_index}].description must be a string.")

    if errors:
        raise ValidationError({"definition": errors})

    return definition


def build_schema_prompt_fragment(definition):
    validate_schema_definition(definition)

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


class CustomSchemaQueryRepository(Protocol):
    def none(self): ...

    def for_owner(self, owner_id): ...

    def count_for_owner(self, owner_id: object) -> int: ...

    def name_exists_for_owner(
        self,
        owner_id: object,
        name: str,
        exclude_pk: object | None = None,
    ) -> bool: ...


class DjangoCustomSchemaQueryRepository:
    def none(self):
        from .models import CustomSchema

        return CustomSchema.objects.none()

    def for_owner(self, owner_id):
        from .models import CustomSchema

        return CustomSchema.objects.filter(owner_id=owner_id)

    def count_for_owner(self, owner_id: object) -> int:
        return self.for_owner(owner_id).count()

    def name_exists_for_owner(
        self,
        owner_id: object,
        name: str,
        exclude_pk: object | None = None,
    ) -> bool:
        queryset = self.for_owner(owner_id).filter(name=name)
        if exclude_pk is not None:
            queryset = queryset.exclude(pk=exclude_pk)
        return queryset.exists()


class CustomSchemaLimitExceededError(Exception):
    """Raised when a user has reached the custom schema creation limit."""


class CustomSchemaPolicyService:
    def __init__(
        self,
        repository: CustomSchemaQueryRepository | None = None,
        max_custom_schemas_per_user: int = MAX_CUSTOM_SCHEMAS_PER_USER,
    ):
        self.repository = repository or DjangoCustomSchemaQueryRepository()
        self.max_custom_schemas_per_user = max_custom_schemas_per_user

    def get_owner_id(self, user) -> object | None:
        owner_id = getattr(user, "id", None)
        if not getattr(user, "is_authenticated", False) or owner_id is None:
            return None
        return owner_id

    def get_queryset_for_user(self, user):
        owner_id = self.get_owner_id(user)
        if owner_id is None:
            return self.repository.none()
        return self.repository.for_owner(owner_id)

    def filter_queryset_by_active(self, queryset, active_value):
        if active_value is None:
            return queryset

        normalized_value = str(active_value).strip().lower()
        if normalized_value in ACTIVE_TRUE_VALUES:
            return queryset.filter(is_active=True)
        if normalized_value in ACTIVE_FALSE_VALUES:
            return queryset.filter(is_active=False)
        return queryset

    def has_name_conflict(self, user, name: str, exclude_pk: object | None = None) -> bool:
        owner_id = self.get_owner_id(user)
        if owner_id is None or not name:
            return False

        return self.repository.name_exists_for_owner(
            owner_id=owner_id,
            name=name,
            exclude_pk=exclude_pk,
        )

    def ensure_can_create_for_user(self, user) -> object | None:
        owner_id = self.get_owner_id(user)
        if owner_id is None:
            return None

        existing_count = self.repository.count_for_owner(owner_id)
        if existing_count >= self.max_custom_schemas_per_user:
            raise CustomSchemaLimitExceededError(
                CUSTOM_SCHEMA_LIMIT_EXCEEDED_ERROR_TEMPLATE.format(
                    max_count=self.max_custom_schemas_per_user
                )
            )

        return owner_id
