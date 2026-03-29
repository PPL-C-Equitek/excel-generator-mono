from rest_framework import serializers

from .models import CustomSchema
from .services import build_schema_prompt_fragment, validate_schema_definition


class CustomSchemaSerializer(serializers.ModelSerializer):
    prompt_fragment = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = CustomSchema
        fields = (
            "id",
            "name",
            "description",
            "version",
            "is_active",
            "definition",
            "prompt_fragment",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "version", "prompt_fragment", "created_at", "updated_at")

    def validate_definition(self, value):
        validate_schema_definition(value)
        return value

    def get_prompt_fragment(self, obj):
        return build_schema_prompt_fragment(obj.definition)
