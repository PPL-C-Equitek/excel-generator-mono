import json
import re
from dataclasses import dataclass
from typing import Any

from file_processing.services.export_service import (
    OutputLLMValidationError,
    validate_output_llm,
)
from llm.services.reasoning_service import (
    LlmReasoningService,
    generate_conversion_reasoning_response,
)


_REASONING_META_KEYS = {"final_answer", "reasoning_steps", "thinking_log"}
_AMBIGUOUS_STRING_VALUES = {
    "unknown",
    "unclear",
    "ambiguous",
    "n/a",
    "na",
    "not sure",
    "not available",
}

_PATH_PATTERN = re.compile(
    r"((?:document_info|content_data\[\d+\])(?:\.[A-Za-z_]\w*)?|summary(?:\['[^']+'\])?)"
)


@dataclass(frozen=True)
class RefinementConfig:
    enabled: bool
    max_iterations: int
    early_exit_on_valid: bool


def _sanitize_reasoning_meta_keys(payload: Any) -> Any:
    if not isinstance(payload, dict):
        return payload
    return {
        key: value for key, value in payload.items() if key not in _REASONING_META_KEYS
    }


def _build_error_issue(message: str) -> dict[str, str]:
    path = "$"
    match = _PATH_PATTERN.search(message)
    if match:
        path = "$." + match.group(1)
    return {
        "path": path,
        "message": message,
        "severity": "error",
    }


def _collect_ambiguity_warnings(payload: Any, path: str = "$") -> list[dict[str, str]]:
    warnings: list[dict[str, str]] = []
    if payload is None:
        warnings.append(
            {
                "path": path,
                "message": "Value is null and may indicate unresolved ambiguity.",
                "severity": "warning",
            }
        )
        return warnings

    if isinstance(payload, str):
        normalized = payload.strip().lower()
        if normalized in _AMBIGUOUS_STRING_VALUES:
            warnings.append(
                {
                    "path": path,
                    "message": f"Value '{payload}' may indicate ambiguous extraction.",
                    "severity": "warning",
                }
            )
        return warnings

    if isinstance(payload, dict):
        for key, value in payload.items():
            warnings.extend(_collect_ambiguity_warnings(value, f"{path}.{key}"))
        return warnings

    if isinstance(payload, list):
        for index, value in enumerate(payload):
            warnings.extend(_collect_ambiguity_warnings(value, f"{path}[{index}]"))
        return warnings

    return warnings


def _normalize_header_value(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower()
    return normalized or None


def _collect_headers_from_header_list(headers: Any) -> set[str]:
    if not isinstance(headers, list):
        return set()
    return {
        normalized
        for normalized in (_normalize_header_value(header) for header in headers)
        if normalized is not None
    }


def _collect_headers_from_rows(rows: Any) -> set[str]:
    if not isinstance(rows, list):
        return set()

    source_headers: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        for row_key in row.keys():
            normalized = _normalize_header_value(row_key)
            if normalized is not None:
                source_headers.add(normalized)
    return source_headers


def _collect_nested_source_headers(payload: Any) -> set[str]:
    if isinstance(payload, dict):
        return _collect_source_headers(payload)
    if isinstance(payload, list):
        source_headers: set[str] = set()
        for item in payload:
            source_headers.update(_collect_source_headers(item))
        return source_headers
    return set()


def _collect_source_headers(payload: Any) -> set[str]:
    if not isinstance(payload, dict):
        return _collect_nested_source_headers(payload)

    source_headers: set[str] = set()
    for key, value in payload.items():
        if key == "headers":
            source_headers.update(_collect_headers_from_header_list(value))
            continue
        if key == "rows":
            source_headers.update(_collect_headers_from_rows(value))
            continue
        source_headers.update(_collect_nested_source_headers(value))
    return source_headers


def _build_quality_error(path: str, message: str) -> dict[str, str]:
    return {
        "path": path,
        "message": message,
        "severity": "error",
    }


def _normalized_headers(headers: Any) -> set[str]:
    if not isinstance(headers, list):
        return set()
    return {
        header.strip().lower()
        for header in headers
        if isinstance(header, str) and header.strip()
    }


def _collect_table_quality_errors(
    table: dict[str, Any],
    table_index: int,
    source_headers: set[str],
) -> tuple[list[dict[str, str]], int]:
    errors: list[dict[str, str]] = []
    total_rows = 0

    rows = table.get("rows")
    if isinstance(rows, list):
        total_rows = len(rows)
        if total_rows == 0:
            errors.append(
                _build_quality_error(
                    f"$.content_data[{table_index}].rows",
                    "rows must not be empty for refinement quality checks.",
                )
            )

    output_headers = _normalized_headers(table.get("headers"))
    has_overlap = bool(output_headers.intersection(source_headers))
    if source_headers and output_headers and not has_overlap:
        errors.append(
            _build_quality_error(
                f"$.content_data[{table_index}].headers",
                (
                    "Output headers do not overlap with source-extracted headers, "
                    "which indicates likely semantic mismatch."
                ),
            )
        )

    return errors, total_rows


def _collect_summary_quality_errors(
    output_json: dict[str, Any],
    total_rows: int,
) -> list[dict[str, str]]:
    summary = output_json.get("summary")
    if not isinstance(summary, dict):
        return []

    total_items = summary.get("total_items")
    if not isinstance(total_items, int) or total_items < 0 or total_items == total_rows:
        return []

    return [
        _build_quality_error(
            "$.summary.total_items",
            "summary.total_items does not match the number of rows in content_data.",
        )
    ]


def _collect_refinement_quality_errors(
    output_json: Any,
    input_json: Any | None,
) -> list[dict[str, str]]:
    if not isinstance(output_json, dict):
        return []

    content_data = output_json.get("content_data")
    if not isinstance(content_data, list):
        return []

    source_headers = _collect_source_headers(input_json) if input_json is not None else set()
    errors: list[dict[str, str]] = []
    total_rows = 0
    for table_index, table in enumerate(content_data):
        if not isinstance(table, dict):
            continue

        table_errors, table_row_count = _collect_table_quality_errors(
            table=table,
            table_index=table_index,
            source_headers=source_headers,
        )
        errors.extend(table_errors)
        total_rows += table_row_count

    errors.extend(_collect_summary_quality_errors(output_json, total_rows))

    return errors


def build_validation_log(
    output_json: Any,
    iteration: int,
    input_json: Any | None = None,
) -> dict[str, Any]:
    structural_errors: list[dict[str, str]] = []
    warnings = _collect_ambiguity_warnings(output_json)
    try:
        validate_output_llm(output_json)
        strict_schema_is_valid = True
    except OutputLLMValidationError as exc:
        message = str(exc).strip() or "Output failed strict export schema validation."
        structural_errors.append(_build_error_issue(message))
        strict_schema_is_valid = False

    quality_errors = _collect_refinement_quality_errors(output_json, input_json=input_json)
    errors = [*structural_errors, *quality_errors]
    verdict = "valid" if strict_schema_is_valid and not quality_errors else "invalid"
    if verdict == "valid":
        summary = "Output passed strict export schema validation."
    elif structural_errors:
        summary = "Output failed strict export schema validation."
    else:
        summary = "Output failed refinement quality checks."

    return {
        "iteration": iteration,
        "verdict": verdict,
        "errors": errors,
        "warnings": warnings,
        "summary": summary,
    }


def _compute_validation_score(validation_log: dict[str, Any]) -> int:
    if validation_log.get("verdict") == "valid":
        return 100
    error_count = len(validation_log.get("errors", []))
    warning_count = len(validation_log.get("warnings", []))
    return max(1, 100 - (15 * error_count) - (2 * warning_count))


def _to_compact_json(value: Any, max_chars: int = 12000) -> str:
    try:
        text = json.dumps(value, ensure_ascii=True)
    except (TypeError, ValueError):
        text = str(value)
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "... [TRUNCATED]"


def build_refinement_instruction(
    previous_output_json: Any,
    validation_log: dict[str, Any],
) -> str:
    return (
        "Use the validation feedback to repair schema issues.\n"
        "Keep top-level output keys exactly: document_info, summary, content_data.\n"
        "Do not include markdown or explanatory text.\n"
        "PREVIOUS_OUTPUT_JSON:\n"
        f"{_to_compact_json(previous_output_json)}\n"
        "VALIDATION_LOG:\n"
        f"{_to_compact_json(validation_log)}\n"
    )


def _build_iteration_input(
    original_input_json: dict[str, Any] | list[Any],
    previous_candidate: Any | None,
    previous_validation_log: dict[str, Any] | None,
) -> tuple[dict[str, Any] | list[Any], str | None]:
    if previous_candidate is None or previous_validation_log is None:
        return original_input_json, None

    refinement_instruction = build_refinement_instruction(
        previous_output_json=previous_candidate,
        validation_log=previous_validation_log,
    )
    current_input_json: dict[str, Any] = {
        "original_input_json": original_input_json,
        "previous_output_json": previous_candidate,
        "validation_log": previous_validation_log,
    }
    return current_input_json, refinement_instruction


def _update_best_candidate(
    best_score: int,
    best_candidate: Any,
    best_log: dict[str, Any] | None,
    candidate: Any,
    validation_log: dict[str, Any],
) -> tuple[int, Any, dict[str, Any] | None, bool]:
    score = _compute_validation_score(validation_log)
    if score < best_score:
        return best_score, best_candidate, best_log, False
    return score, candidate, validation_log, True


def _maybe_generate_reasoning(
    current_reasoning: Any,
    include_reasoning: bool,
    reasoning_service: LlmReasoningService | None,
    input_json: dict[str, Any] | list[Any],
    output_json: Any,
    file_name: str,
    document_type: str,
) -> Any:
    if not include_reasoning or reasoning_service is None:
        return current_reasoning

    try:
        return generate_conversion_reasoning_response(
            reasoning_service=reasoning_service,
            input_json=input_json,
            output_json=output_json,
            file_name=file_name,
            document_type=document_type,
        )
    except Exception:
        return current_reasoning


def _resolve_refinement_final_status(has_valid_candidate: bool, best_candidate: Any) -> str:
    if has_valid_candidate:
        return "valid"
    if best_candidate is not None:
        return "best_effort"
    return "failed"


class RefinementOrchestrator:
    def __init__(
        self,
        generation_service,
        reasoning_service: LlmReasoningService | None = None,
    ):
        self.generation_service = generation_service
        self.reasoning_service = reasoning_service

    def run(
        self,
        input_json: dict[str, Any] | list[Any],
        custom_schema_id,
        include_reasoning: bool,
        refinement_config: RefinementConfig,
        chat_context: str | None = None,
        file_name: str = "unknown",
        document_type: str = "unknown",
    ) -> dict[str, Any]:
        first_candidate = None
        best_candidate = None
        best_log = None
        best_score = -1
        latest_reasoning = None
        best_reasoning = None
        iterations_run = 0
        early_exit_triggered = False
        has_valid_candidate = False

        previous_candidate = None
        previous_validation_log = None
        max_iterations = max(1, refinement_config.max_iterations)
        for iteration in range(1, max_iterations + 1):
            iterations_run = iteration
            current_input_json, refinement_instruction = _build_iteration_input(
                original_input_json=input_json,
                previous_candidate=previous_candidate,
                previous_validation_log=previous_validation_log,
            )

            generated_candidate = self.generation_service.generate(
                input_json=current_input_json,
                custom_schema_id=custom_schema_id,
                refinement_instruction=refinement_instruction,
                chat_context=chat_context,
            )
            sanitized_candidate = _sanitize_reasoning_meta_keys(generated_candidate)
            if first_candidate is None:
                first_candidate = sanitized_candidate

            validation_log = build_validation_log(
                sanitized_candidate,
                iteration=iteration,
                input_json=input_json,
            )
            latest_reasoning = _maybe_generate_reasoning(
                current_reasoning=latest_reasoning,
                include_reasoning=include_reasoning,
                reasoning_service=self.reasoning_service,
                input_json=input_json,
                output_json=sanitized_candidate,
                file_name=file_name,
                document_type=document_type,
            )
            best_score, best_candidate, best_log, did_update_best = _update_best_candidate(
                best_score=best_score,
                best_candidate=best_candidate,
                best_log=best_log,
                candidate=sanitized_candidate,
                validation_log=validation_log,
            )
            if did_update_best:
                best_reasoning = latest_reasoning

            is_valid = validation_log["verdict"] == "valid"
            has_valid_candidate = has_valid_candidate or is_valid
            if is_valid and refinement_config.early_exit_on_valid:
                early_exit_triggered = True
                break

            previous_candidate = sanitized_candidate
            previous_validation_log = validation_log

        final_status = _resolve_refinement_final_status(
            has_valid_candidate=has_valid_candidate,
            best_candidate=best_candidate,
        )

        return {
            "raw_json": first_candidate,
            "validated_json": best_candidate,
            "output_json": best_candidate,
            "validation_log": best_log,
            "reasoning": best_reasoning if include_reasoning else None,
            "refinement_meta": {
                "iterations_run": iterations_run,
                "max_iterations": max_iterations,
                "early_exit_triggered": early_exit_triggered,
                "final_status": final_status,
            },
        }
