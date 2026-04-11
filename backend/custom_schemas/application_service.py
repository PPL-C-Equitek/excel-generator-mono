from .constants import CUSTOM_SCHEMA_LIMIT_EXCEEDED_ERROR_TEMPLATE
from .policy_service import CustomSchemaPolicyService


class CustomSchemaApplicationService:
    def __init__(
        self,
        policy_service: CustomSchemaPolicyService | None = None,
    ):
        self.policy_service = policy_service or CustomSchemaPolicyService()

    def get_owner_id(self, user) -> object | None:
        return self.policy_service.get_owner_id(user)

    def get_queryset_for_user(self, user):
        return self.policy_service.get_queryset_for_user(user)

    def get_filtered_queryset_for_user(self, user, active_value):
        return self.policy_service.filter_queryset_by_active(
            queryset=self.get_queryset_for_user(user),
            active_value=active_value,
        )

    def has_name_conflict(
        self,
        user,
        name: str,
        exclude_pk: object | None = None,
    ) -> bool:
        return self.policy_service.has_name_conflict(
            user=user,
            name=name,
            exclude_pk=exclude_pk,
        )

    def get_create_owner_id(self, user) -> object | None:
        return self.policy_service.ensure_can_create_for_user(user)

    def get_limit_exceeded_message(self) -> str:
        return CUSTOM_SCHEMA_LIMIT_EXCEEDED_ERROR_TEMPLATE.format(
            max_count=self.policy_service.max_custom_schemas_per_user
        )
