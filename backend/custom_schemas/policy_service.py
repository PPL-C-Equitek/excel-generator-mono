from .constants import (
    ACTIVE_FALSE_VALUES,
    ACTIVE_TRUE_VALUES,
    CUSTOM_SCHEMA_LIMIT_EXCEEDED_ERROR_TEMPLATE,
    MAX_CUSTOM_SCHEMAS_PER_USER,
)
from .repositories import CustomSchemaQueryRepository, DjangoCustomSchemaQueryRepository


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
