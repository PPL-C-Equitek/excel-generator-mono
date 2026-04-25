from rest_framework import serializers


REASONING_META_KEYS = {"final_answer", "reasoning_steps", "thinking_log"}


class LlmGenerateRequestSerializer(serializers.Serializer):
    input_json = serializers.JSONField()
    custom_schema_id = serializers.UUIDField(required=False, allow_null=True)
    include_reasoning = serializers.BooleanField(required=False, default=True)

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


class ReasoningPayloadSerializer(serializers.Serializer):
    final_answer = serializers.CharField(trim_whitespace=True, allow_blank=False)
    reasoning_steps = serializers.ListField(
        child=serializers.CharField(trim_whitespace=True, allow_blank=False),
        allow_empty=False,
    )
    thinking_log = serializers.CharField(trim_whitespace=True, allow_blank=False)


class LlmGenerateResponseSerializer(serializers.Serializer):
    output_json = serializers.JSONField()
    reasoning = ReasoningPayloadSerializer(required=False, allow_null=True)

    def validate_output_json(self, value):
        if isinstance(value, dict):
            conflicting_keys = sorted(REASONING_META_KEYS.intersection(value.keys()))
            if conflicting_keys:
                raise serializers.ValidationError(
                    "output_json must not include reasoning fields: "
                    + ", ".join(conflicting_keys)
                )

        return value


class LlmReasoningRequestSerializer(serializers.Serializer):
    prompt = serializers.CharField(trim_whitespace=True, allow_blank=False)

    def validate(self, attrs):
        if "model" in getattr(self, "initial_data", {}):
            raise serializers.ValidationError(
                {"model": "Field 'model' is not allowed. Model is configured by server."}
            )
        return attrs


class LlmReasoningResponseSerializer(ReasoningPayloadSerializer):
    pass

