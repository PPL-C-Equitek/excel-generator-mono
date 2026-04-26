from io import StringIO

from rest_framework import serializers

MAX_MESSAGE_LENGTH = 4096

class LlmGenerateRequestSerializer(serializers.Serializer):
    input_json = serializers.JSONField()
    session_id = serializers.UUIDField(required=False, allow_null=True)
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
    session_id = serializers.UUIDField(required=False, allow_null=True)


class SendMessageRequestSerializer(serializers.Serializer):
    session_id = serializers.UUIDField(required=False, allow_null=True)
    message = serializers.CharField(
        max_length=MAX_MESSAGE_LENGTH,
        allow_blank=False,
        trim_whitespace=False,
    )

    def validate_message(self, value):
        if not value.strip():
            raise serializers.ValidationError("This field may not be blank.")
        return value


class SendMessageResponseSerializer(serializers.Serializer):
    session_id = serializers.UUIDField()
    reply = serializers.CharField()


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


def _extract_normalized_thinking_log(output_json) -> str:
    if not isinstance(output_json, dict):
        return ""

    raw_thinking_log = output_json.get("thinking_log")
    if not isinstance(raw_thinking_log, str):
        return ""

    return raw_thinking_log.strip()


def _is_safe_thinking_log_line(line: str) -> bool:
    lowered_line = line.lower()
    return not any(marker in lowered_line for marker in _THINKING_LOG_BLOCKED_MARKERS)


def _append_safe_line_with_limit(
    safe_lines: list[str],
    current_length: int,
    line: str,
) -> tuple[int, bool]:
    separator_length = 1 if safe_lines else 0
    remaining_chars = THINKING_LOG_MAX_CHARS - current_length - separator_length
    if remaining_chars <= 0:
        return current_length, False

    if len(line) > remaining_chars:
        safe_lines.append(line[:remaining_chars])
        return current_length, False

    if separator_length:
        current_length += 1

    safe_lines.append(line)
    current_length += len(line)
    return current_length, True


def _safe_thinking_log_summary(output_json) -> str:
    normalized = _extract_normalized_thinking_log(output_json)
    if not normalized:
        return ""

    safe_lines = []
    current_length = 0
    for line in StringIO(normalized):
        trimmed_line = line.strip()
        if not trimmed_line:
            continue

        if not _is_safe_thinking_log_line(trimmed_line):
            continue

        current_length, should_continue = _append_safe_line_with_limit(
            safe_lines=safe_lines,
            current_length=current_length,
            line=trimmed_line,
        )
        if not should_continue:
            break

    if not safe_lines:
        return ""

    return "\n".join(safe_lines)


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
