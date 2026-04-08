from rest_framework import generics
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated

from authentication.permissions import IsVerifiedUser
from .serializers import CustomSchemaSerializer
from .application_service import CustomSchemaApplicationService
from .policy_service import CustomSchemaLimitExceededError


class UserOwnedCustomSchemaMixin:
    permission_classes = [IsAuthenticated, IsVerifiedUser]
    application_service_class = CustomSchemaApplicationService

    def get_application_service(self) -> CustomSchemaApplicationService:
        return self.application_service_class()

    def get_current_user_id(self):
        return self.get_application_service().get_owner_id(self.request.user)

    def get_base_queryset(self):
        return self.get_application_service().get_queryset_for_user(
            self.request.user
        )

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["application_service"] = self.get_application_service()
        return context


class CustomSchemaListCreateView(UserOwnedCustomSchemaMixin, generics.ListCreateAPIView):
    serializer_class = CustomSchemaSerializer

    def get_queryset(self):
        return self.get_application_service().get_filtered_queryset_for_user(
            user=self.request.user,
            active_value=self.request.query_params.get("active"),
        )

    def perform_create(self, serializer):
        application_service = self.get_application_service()
        try:
            owner_id = application_service.get_create_owner_id(self.request.user)
        except CustomSchemaLimitExceededError as exc:
            raise ValidationError(
                {
                    "message": application_service.get_limit_exceeded_message()
                }
            ) from exc

        serializer.save(owner_id=owner_id)


class CustomSchemaDetailView(
    UserOwnedCustomSchemaMixin, generics.RetrieveUpdateDestroyAPIView
):
    serializer_class = CustomSchemaSerializer

    def get_queryset(self):
        return self.get_base_queryset()
