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


class LlmReasoningRequestSerializer(serializers.Serializer):
    prompt = serializers.CharField(trim_whitespace=True, allow_blank=False)

    def validate(self, attrs):
        if "model" in getattr(self, "initial_data", {}):
            raise serializers.ValidationError(
                {"model": "Field 'model' is not allowed. Model is configured by server."}
            )
        return attrs


class LlmReasoningResponseSerializer(serializers.Serializer):
    final_answer = serializers.CharField(trim_whitespace=True, allow_blank=False)
    reasoning_steps = serializers.ListField(
        child=serializers.CharField(trim_whitespace=True, allow_blank=False),
        allow_empty=False,
    )
    thinking_log = serializers.CharField(trim_whitespace=True, allow_blank=False)


THINKING_LOG_MAX_CHARS = 2000
_THINKING_LOG_BLOCKED_MARKERS = (
    "chain-of-thought",
    "internal prompt",
    "system prompt",
    "api key",
    "secret",
    "token",
    "debug",
    "traceback",
    "stack trace",
)


def _safe_thinking_log_summary(output_json) -> str:
    if not isinstance(output_json, dict):
        return ""

    raw_thinking_log = output_json.get("thinking_log")
    if not isinstance(raw_thinking_log, str):
        return ""

    normalized = raw_thinking_log.strip()
    if not normalized:
        return ""

    safe_lines = []
    for line in normalized.splitlines():
        trimmed_line = line.strip()
        if not trimmed_line:
            continue
        lowered_line = trimmed_line.lower()
        if any(marker in lowered_line for marker in _THINKING_LOG_BLOCKED_MARKERS):
            continue
        safe_lines.append(trimmed_line)

    if not safe_lines:
        return ""

    return "\n".join(safe_lines)[:THINKING_LOG_MAX_CHARS]


class ThinkingLogItemSerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    session_id = serializers.CharField(read_only=True, allow_blank=True, allow_null=True)
    request_id = serializers.CharField(read_only=True, allow_blank=True, allow_null=True)
    thinking_log = serializers.CharField(read_only=True, allow_blank=True)
    status_processing = serializers.CharField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)

    def to_representation(self, instance):
        output_json = instance.output_json if isinstance(instance.output_json, dict) else {}
        return {
            "id": str(instance.id),
            "session_id": output_json.get("session_id"),
            "request_id": output_json.get("request_id"),
            "thinking_log": _safe_thinking_log_summary(output_json),
            "status_processing": instance.status_processing,
            "created_at": instance.created_at,
        }

