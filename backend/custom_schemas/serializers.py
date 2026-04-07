from rest_framework import serializers

from .models import CustomSchema
from .application_service import CustomSchemaApplicationService
from .constants import CUSTOM_SCHEMA_DUPLICATE_NAME_ERROR_MESSAGE
from .definition_service import (
    build_schema_prompt_fragment,
    validate_schema_definition,
)


class CustomSchemaSerializer(serializers.ModelSerializer):
    prompt_fragment = serializers.SerializerMethodField(read_only=True)
    owner_id = serializers.UUIDField(read_only=True)

    class Meta:
        model = CustomSchema
        fields = (
            "id",
            "owner_id",
            "name",
            "description",
            "is_active",
            "definition",
            "prompt_fragment",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "owner_id",
            "prompt_fragment",
            "created_at",
            "updated_at",
        )

    def validate_definition(self, value):
        validate_schema_definition(value)
        return value

    def get_application_service(self) -> CustomSchemaApplicationService:
        application_service = self.context.get("application_service")
        if application_service is not None:
            return application_service
        return CustomSchemaApplicationService()

    def validate_name(self, value):
        request = self.context.get("request")
        owner = getattr(request, "user", None)
        exclude_pk = getattr(self.instance, "pk", None)
        if not self.get_application_service().has_name_conflict(
            user=owner,
            name=value,
            exclude_pk=exclude_pk,
        ):
            return value
        raise serializers.ValidationError(
            CUSTOM_SCHEMA_DUPLICATE_NAME_ERROR_MESSAGE
        )

    def get_prompt_fragment(self, obj):
        return build_schema_prompt_fragment(obj.definition)
