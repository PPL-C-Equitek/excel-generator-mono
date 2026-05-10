from io import StringIO

from rest_framework import serializers

MAX_MESSAGE_LENGTH = 4096

REASONING_META_KEYS = {"final_answer", "reasoning_steps", "thinking_log"}


class LlmGenerateRequestSerializer(serializers.Serializer):
    input_json = serializers.JSONField()
    session_id = serializers.UUIDField(required=False, allow_null=True)
    chat_id = serializers.UUIDField(required=False, allow_null=True)
    target_output_id = serializers.UUIDField(required=False, allow_null=True)
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
    session_id = serializers.UUIDField(required=False, allow_null=True)
    chat_id = serializers.UUIDField(required=False, allow_null=True)
    output_id = serializers.UUIDField(required=False, allow_null=True)
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


class SendMessageRequestSerializer(serializers.Serializer):
    session_id = serializers.UUIDField(required=False, allow_null=True)
    target_output_id = serializers.UUIDField(required=False, allow_null=True)
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
    chat_id = serializers.UUIDField()
    reply = serializers.CharField()


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
    chat_id = serializers.CharField(read_only=True, allow_blank=True, allow_null=True)
    thinking_log = serializers.CharField(read_only=True, allow_blank=True)
    reasoning = serializers.ListField(child=serializers.CharField(), read_only=True)
    status_processing = serializers.CharField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)

    def to_representation(self, instance):
        output_json = instance.output_json if isinstance(getattr(instance, "output_json", None), dict) else {}

        session_id = getattr(instance, "session_id", None)
        chat_id = getattr(instance, "source_message_id", None)
        if chat_id is None:
            chat_id = output_json.get("chat_id")

        thinking_log = getattr(instance, "thinking_log", None)
        if thinking_log is None:
            thinking_log = _safe_thinking_log_summary(output_json)

        reasoning_payload = getattr(instance, "reasoning", None)
        if not isinstance(reasoning_payload, dict):
            reasoning_payload = {}

        reasoning_steps = reasoning_payload.get("reasoning_steps")
        if not isinstance(reasoning_steps, list):
            reasoning_steps = []

        return {
            "id": str(instance.id),
            "session_id": str(session_id) if session_id is not None else None,
            "chat_id": str(chat_id) if chat_id is not None else None,
            "thinking_log": thinking_log,
            "reasoning": reasoning_steps,
            "status_processing": getattr(instance, "status_processing", "completed"),
            "created_at": instance.created_at,
        }
