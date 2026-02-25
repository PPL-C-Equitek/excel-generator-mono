from rest_framework import serializers


class LlmGenerateRequestSerializer(serializers.Serializer):
    input_json = serializers.JSONField()
    model = serializers.CharField(required=False, allow_blank=False)

    def validate_input_json(self, value):
        if not isinstance(value, (dict, list)):
            raise serializers.ValidationError(
                "Field 'input_json' must be a JSON object or array."
            )
        return value


class LlmGenerateResponseSerializer(serializers.Serializer):
    output_json = serializers.JSONField()

