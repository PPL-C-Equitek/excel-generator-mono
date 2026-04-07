from rest_framework import serializers

from .models import CustomSchema
from .services import (
    CustomSchemaPolicyService,
    CUSTOM_SCHEMA_DUPLICATE_NAME_ERROR_MESSAGE,
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

    def get_policy_service(self) -> CustomSchemaPolicyService:
        policy_service = self.context.get("policy_service")
        if policy_service is not None:
            return policy_service
        return CustomSchemaPolicyService()

    def validate_name(self, value):
        request = self.context.get("request")
        owner = getattr(request, "user", None)
        exclude_pk = getattr(self.instance, "pk", None)
        if not self.get_policy_service().has_name_conflict(
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
