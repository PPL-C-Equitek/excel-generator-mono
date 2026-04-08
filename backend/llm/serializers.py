from rest_framework import serializers


class LlmGenerateRequestSerializer(serializers.Serializer):
    input_json = serializers.JSONField()
    custom_schema_id = serializers.UUIDField(required=False, allow_null=True)

    def validate_input_json(self, value):
        if not isinstance(value, (dict, list)):
            raise serializers.ValidationError(
                "Field 'input_json' must be a JSON object or array."
            )
        return value

    def validate(self, attrs):
        if "model" in getattr(self, "initial_data", {}):
            raise serializers.ValidationError(
                {"model": "Field 'model' is not allowed. Model is configured by server."}
            )
        return attrs


class LlmGenerateResponseSerializer(serializers.Serializer):
    output_json = serializers.JSONField()

