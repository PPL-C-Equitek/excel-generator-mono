from rest_framework import generics
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated

from .serializers import CustomSchemaSerializer
from .services import (
    CUSTOM_SCHEMA_LIMIT_EXCEEDED_ERROR_TEMPLATE,
    MAX_CUSTOM_SCHEMAS_PER_USER,
    CustomSchemaLimitExceededError,
    CustomSchemaPolicyService,
)


class UserOwnedCustomSchemaMixin:
    permission_classes = [IsAuthenticated]
    policy_service_class = CustomSchemaPolicyService

    def get_policy_service(self) -> CustomSchemaPolicyService:
        return self.policy_service_class()

    def get_current_user_id(self):
        return self.get_policy_service().get_owner_id(self.request.user)

    def get_base_queryset(self):
        return self.get_policy_service().get_queryset_for_user(self.request.user)


class CustomSchemaListCreateView(UserOwnedCustomSchemaMixin, generics.ListCreateAPIView):
    serializer_class = CustomSchemaSerializer

    def get_queryset(self):
        return self.get_policy_service().filter_queryset_by_active(
            queryset=self.get_base_queryset(),
            active_value=self.request.query_params.get("active"),
        )

    def perform_create(self, serializer):
        try:
            owner_id = self.get_policy_service().ensure_can_create_for_user(
                self.request.user
            )
        except CustomSchemaLimitExceededError as exc:
            raise ValidationError(
                {
                    "message": CUSTOM_SCHEMA_LIMIT_EXCEEDED_ERROR_TEMPLATE.format(
                        max_count=MAX_CUSTOM_SCHEMAS_PER_USER
                    )
                }
            ) from exc

        serializer.save(owner_id=owner_id)


class CustomSchemaDetailView(
    UserOwnedCustomSchemaMixin, generics.RetrieveUpdateDestroyAPIView
):
    serializer_class = CustomSchemaSerializer

    def get_queryset(self):
        return self.get_base_queryset()
