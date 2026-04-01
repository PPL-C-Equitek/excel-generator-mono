from rest_framework import serializers

from .models import CustomSchema
from .services import build_schema_prompt_fragment, validate_schema_definition


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
            "version",
            "is_active",
            "definition",
            "prompt_fragment",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "owner_id",
            "version",
            "prompt_fragment",
            "created_at",
            "updated_at",
        )

    def validate_definition(self, value):
        validate_schema_definition(value)
        return value

    def validate_name(self, value):
        request = self.context.get("request")
        owner = getattr(request, "user", None)
        owner_id = getattr(owner, "id", None)

        if (
            not owner
            or not getattr(owner, "is_authenticated", False)
            or owner_id is None
            or not value
        ):
            return value

        existing = CustomSchema.objects.filter(owner_id=owner_id, name=value)
        if self.instance is not None:
            existing = existing.exclude(pk=self.instance.pk)

        if existing.exists():
            raise serializers.ValidationError(
                "Anda sudah memiliki custom schema dengan nama ini."
            )

        return value

    def get_prompt_fragment(self, obj):
        return build_schema_prompt_fragment(obj.definition)
