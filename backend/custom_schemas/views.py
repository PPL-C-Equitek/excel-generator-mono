from rest_framework import generics
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated

from .models import CustomSchema
from .serializers import CustomSchemaSerializer


MAX_CUSTOM_SCHEMAS_PER_USER = 5


class UserOwnedCustomSchemaMixin:
    permission_classes = [IsAuthenticated]

    def get_current_user_id(self):
        user_id = getattr(self.request.user, "id", None)
        if user_id is None:
            return None
        return user_id

    def get_base_queryset(self):
        user = self.request.user
        user_id = self.get_current_user_id()
        if not getattr(user, "is_authenticated", False) or user_id is None:
            return CustomSchema.objects.none()
        return CustomSchema.objects.filter(owner_id=user_id)


class CustomSchemaListCreateView(UserOwnedCustomSchemaMixin, generics.ListCreateAPIView):
    serializer_class = CustomSchemaSerializer

    def get_queryset(self):
        queryset = self.get_base_queryset()
        active = self.request.query_params.get("active")
        if active is None:
            return queryset

        normalized = active.strip().lower()
        if normalized in {"true", "1", "yes"}:
            return queryset.filter(is_active=True)
        if normalized in {"false", "0", "no"}:
            return queryset.filter(is_active=False)
        return queryset

    def perform_create(self, serializer):
        owner_id = self.get_current_user_id()
        existing_count = self.get_base_queryset().count()
        if existing_count >= MAX_CUSTOM_SCHEMAS_PER_USER:
            raise ValidationError(
                {
                    "message": (
                        f"Maksimal {MAX_CUSTOM_SCHEMAS_PER_USER} custom schemas per user."
                    )
                }
            )

        serializer.save(owner_id=owner_id)


class CustomSchemaDetailView(
    UserOwnedCustomSchemaMixin, generics.RetrieveUpdateDestroyAPIView
):
    serializer_class = CustomSchemaSerializer

    def get_queryset(self):
        return self.get_base_queryset()
