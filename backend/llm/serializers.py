from io import StringIO

from rest_framework import serializers
from django.conf import settings

MAX_MESSAGE_LENGTH = 4096

REASONING_META_KEYS = {"final_answer", "reasoning_steps", "thinking_log"}
REFINEMENT_FINAL_STATUS_CHOICES = ("valid", "best_effort", "failed")


def _resolved_refinement_default_max_iterations() -> int:
    raw_value = getattr(settings, "LLM_REFINEMENT_DEFAULT_MAX_ITER", 3)
    return raw_value if isinstance(raw_value, int) and raw_value > 0 else 3


def _resolved_refinement_max_iterations_cap() -> int:
    raw_value = getattr(settings, "LLM_REFINEMENT_MAX_ITER_CAP", 3)
    return raw_value if isinstance(raw_value, int) and raw_value > 0 else 3


def _resolved_refinement_default_payload() -> dict[str, object]:
    default_max_iterations = _resolved_refinement_default_max_iterations()
    return {
        "enabled": True,
        "max_iterations": default_max_iterations,
        "early_exit_on_valid": True,
    }


class LlmGenerateRefinementRequestSerializer(serializers.Serializer):
    enabled = serializers.BooleanField(required=False, default=True)
    max_iterations = serializers.IntegerField(
        required=False,
        min_value=1,
    )
    early_exit_on_valid = serializers.BooleanField(required=False, default=True)

    def validate_max_iterations(self, value):
        max_cap = _resolved_refinement_max_iterations_cap()
        if value > max_cap:
            raise serializers.ValidationError(
                f"max_iterations must be less than or equal to {max_cap}."
            )
        return value

    def validate(self, attrs):
        normalized = {
            "enabled": attrs.get("enabled", True),
            "max_iterations": attrs.get(
                "max_iterations",
                _resolved_refinement_default_max_iterations(),
            ),
            "early_exit_on_valid": attrs.get("early_exit_on_valid", True),
        }
        return normalized


class LlmGenerateRequestSerializer(serializers.Serializer):
    input_json = serializers.JSONField()
    custom_schema_id = serializers.UUIDField(required=False, allow_null=True)
    include_reasoning = serializers.BooleanField(required=False, default=True)
    refinement = LlmGenerateRefinementRequestSerializer(required=False)

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
        attrs["refinement"] = attrs.get("refinement", _resolved_refinement_default_payload())
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
    raw_json = serializers.JSONField(required=False)
    validated_json = serializers.JSONField(required=False)
    validation_log = serializers.JSONField(required=False)
    refinement_meta = serializers.JSONField(required=False)

    def validate_output_json(self, value):
        if isinstance(value, dict):
            conflicting_keys = sorted(REASONING_META_KEYS.intersection(value.keys()))
            if conflicting_keys:
                raise serializers.ValidationError(
                    "output_json must not include reasoning fields: "
                    + ", ".join(conflicting_keys)
                )

        return value

    def validate_validation_log(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("validation_log must be an object.")

        required_keys = {"iteration", "verdict", "errors", "warnings", "summary"}
        missing_keys = sorted(required_keys.difference(value.keys()))
        if missing_keys:
            raise serializers.ValidationError(
                "validation_log is missing required keys: " + ", ".join(missing_keys)
            )

        for issues_key in ("errors", "warnings"):
            issues = value.get(issues_key)
            if not isinstance(issues, list):
                raise serializers.ValidationError(f"validation_log.{issues_key} must be a list.")
            for issue in issues:
                if not isinstance(issue, dict):
                    raise serializers.ValidationError(
                        f"validation_log.{issues_key} items must be objects."
                    )
                for required_field in ("path", "message", "severity"):
                    issue_value = issue.get(required_field)
                    if not isinstance(issue_value, str) or not issue_value.strip():
                        raise serializers.ValidationError(
                            f"validation_log.{issues_key} items must include non-empty {required_field}."
                        )

        verdict = value.get("verdict")
        if verdict not in {"valid", "invalid"}:
            raise serializers.ValidationError(
                "validation_log.verdict must be either 'valid' or 'invalid'."
            )

        if not isinstance(value.get("iteration"), int) or value["iteration"] < 1:
            raise serializers.ValidationError(
                "validation_log.iteration must be a positive integer."
            )

        summary = value.get("summary")
        if not isinstance(summary, str) or not summary.strip():
            raise serializers.ValidationError("validation_log.summary must be a non-empty string.")

        return value

    def validate_refinement_meta(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("refinement_meta must be an object.")

        required_keys = {
            "iterations_run",
            "max_iterations",
            "early_exit_triggered",
            "final_status",
        }
        missing_keys = sorted(required_keys.difference(value.keys()))
        if missing_keys:
            raise serializers.ValidationError(
                "refinement_meta is missing required keys: " + ", ".join(missing_keys)
            )

        if not isinstance(value.get("iterations_run"), int) or value["iterations_run"] < 1:
            raise serializers.ValidationError(
                "refinement_meta.iterations_run must be a positive integer."
            )
        if not isinstance(value.get("max_iterations"), int) or value["max_iterations"] < 1:
            raise serializers.ValidationError(
                "refinement_meta.max_iterations must be a positive integer."
            )
        if not isinstance(value.get("early_exit_triggered"), bool):
            raise serializers.ValidationError(
                "refinement_meta.early_exit_triggered must be a boolean."
            )

        final_status = value.get("final_status")
        if final_status not in REFINEMENT_FINAL_STATUS_CHOICES:
            raise serializers.ValidationError(
                "refinement_meta.final_status must be one of: "
                + ", ".join(REFINEMENT_FINAL_STATUS_CHOICES)
            )

        return value


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
