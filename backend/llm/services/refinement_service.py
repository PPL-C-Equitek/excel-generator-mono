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
_REFINEMENT_PREVIOUS_OUTPUT_MAX_CHARS = 6000
_REFINEMENT_VALIDATION_LOG_MAX_CHARS = 3000
_REFINEMENT_MAX_ISSUES_IN_INSTRUCTION = 12
_DEFAULT_REFINEMENT_PLATEAU_PATIENCE = 2
_LOW_CONFIDENCE_OCR_THRESHOLD = 60.0


@dataclass(frozen=True)
class RefinementConfig:
    enabled: bool
    max_iterations: int
    early_exit_on_valid: bool
    early_exit_on_plateau: bool = True
    plateau_patience: int = _DEFAULT_REFINEMENT_PLATEAU_PATIENCE


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


def _extract_ocr_confidence(payload: Any) -> float | None:
    if not isinstance(payload, dict):
        return None

    ocr_metadata = payload.get("ocr_metadata")
    if isinstance(ocr_metadata, dict):
        confidence_score = ocr_metadata.get("confidence_score")
        if isinstance(confidence_score, (int, float)):
            return float(confidence_score)

    for nested_key in ("original_input_json", "input_json", "payload"):
        nested_payload = payload.get(nested_key)
        confidence = _extract_ocr_confidence(nested_payload)
        if confidence is not None:
            return confidence

    return None


def _collect_table_quality_errors(
    table: dict[str, Any],
    table_index: int,
    source_headers: set[str],
    relax_header_checks: bool = False,
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
    if source_headers and output_headers and not has_overlap and not relax_header_checks:
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
    if not isinstance(total_items, int):
        return []

    if total_items < 0:
        return [
            _build_quality_error(
                "$.summary.total_items",
                "summary.total_items must be a non-negative integer.",
            )
        ]

    if total_items == total_rows:
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
    ocr_confidence = _extract_ocr_confidence(input_json)
    # Do NOT relax header checks when OCR confidence is low. Instead,
    # treat low OCR confidence as a blocking quality issue that requires
    # manual review so the pipeline does not accept semantically-incorrect
    # outputs produced from noisy OCR inputs.
    relax_header_checks = False
    errors: list[dict[str, str]] = []
    total_rows = 0
    for table_index, table in enumerate(content_data):
        if not isinstance(table, dict):
            continue

        table_errors, table_row_count = _collect_table_quality_errors(
            table=table,
            table_index=table_index,
            source_headers=source_headers,
            relax_header_checks=relax_header_checks,
        )
        errors.extend(table_errors)
        total_rows += table_row_count

    # If OCR confidence is low, add an explicit quality error to force
    # manual review / block automatic acceptance.
    if ocr_confidence is not None and ocr_confidence < _LOW_CONFIDENCE_OCR_THRESHOLD:
        errors.append(
            _build_quality_error(
                "$.ocr_metadata.confidence_score",
                (
                    f"Input OCR confidence is {ocr_confidence:.1f}% (<{_LOW_CONFIDENCE_OCR_THRESHOLD:.1f}%). "
                    "Low OCR confidence prevents relaxing header validation — manual review required."
                ),
            )
        )

    errors.extend(_collect_summary_quality_errors(output_json, total_rows))

    return errors


def build_validation_log(
    output_json: Any,
    iteration: int,
    input_json: Any | None = None,
) -> dict[str, Any]:
    structural_errors: list[dict[str, str]] = []
    warnings = _collect_ambiguity_warnings(output_json)
    ocr_confidence = _extract_ocr_confidence(input_json)
    if ocr_confidence is not None and ocr_confidence < _LOW_CONFIDENCE_OCR_THRESHOLD:
        warnings.append(
            {
                "path": "$.ocr_metadata.confidence_score",
                "message": (
                    f"Input OCR confidence is {ocr_confidence:.1f}% (<{_LOW_CONFIDENCE_OCR_THRESHOLD:.1f}%). "
                    "Low OCR confidence — stricter validation applied and manual review recommended."
                ),
                "severity": "warning",
            }
        )
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


def _compact_validation_issues(issues: Any, max_items: int) -> list[dict[str, str]]:
    if not isinstance(issues, list):
        return []

    compact_issues: list[dict[str, str]] = []
    for issue in issues:
        if not isinstance(issue, dict):
            continue
        path = issue.get("path")
        message = issue.get("message")
        severity = issue.get("severity")
        if not all(isinstance(value, str) and value.strip() for value in (path, message, severity)):
            continue
        compact_issues.append(
            {
                "path": path.strip(),
                "message": message.strip(),
                "severity": severity.strip(),
            }
        )
        if len(compact_issues) >= max_items:
            break

    return compact_issues


def _compact_validation_log_for_instruction(validation_log: Any) -> Any:
    if not isinstance(validation_log, dict):
        return validation_log

    errors = validation_log.get("errors")
    warnings = validation_log.get("warnings")
    compact_errors = _compact_validation_issues(
        errors,
        max_items=_REFINEMENT_MAX_ISSUES_IN_INSTRUCTION,
    )
    compact_warnings = _compact_validation_issues(
        warnings,
        max_items=max(1, _REFINEMENT_MAX_ISSUES_IN_INSTRUCTION // 3),
    )

    return {
        "iteration": validation_log.get("iteration"),
        "verdict": validation_log.get("verdict"),
        "summary": validation_log.get("summary"),
        "error_count": len(errors) if isinstance(errors, list) else 0,
        "warning_count": len(warnings) if isinstance(warnings, list) else 0,
        "errors": compact_errors,
        "warnings": compact_warnings,
    }


def build_refinement_instruction(
    previous_output_json: Any,
    validation_log: dict[str, Any],
) -> str:
    compact_validation_log = _compact_validation_log_for_instruction(validation_log)
    return (
        "Use the validation feedback to repair schema issues.\n"
        "Keep top-level output keys exactly: document_info, summary, content_data.\n"
        "Do not include markdown or explanatory text.\n"
        "PREVIOUS_OUTPUT_JSON:\n"
        f"{_to_compact_json(previous_output_json, max_chars=_REFINEMENT_PREVIOUS_OUTPUT_MAX_CHARS)}\n"
        "VALIDATION_LOG:\n"
        f"{_to_compact_json(compact_validation_log, max_chars=_REFINEMENT_VALIDATION_LOG_MAX_CHARS)}\n"
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
        "validation_log": _compact_validation_log_for_instruction(previous_validation_log),
    }
    return current_input_json, refinement_instruction


def _update_best_candidate(
    best_score: int,
    best_candidate: Any,
    best_log: dict[str, Any] | None,
    candidate: Any,
    validation_log: dict[str, Any],
) -> tuple[int, Any, dict[str, Any] | None]:
    score = _compute_validation_score(validation_log)
    if score < best_score:
        return best_score, best_candidate, best_log
    return score, candidate, validation_log


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
        iterations_run = 0
        early_exit_triggered = False
        has_valid_candidate = False
        stagnation_count = 0
        plateau_patience = max(1, int(refinement_config.plateau_patience))

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
            previous_best_score = best_score
            best_score, best_candidate, best_log = _update_best_candidate(
                best_score=best_score,
                best_candidate=best_candidate,
                best_log=best_log,
                candidate=sanitized_candidate,
                validation_log=validation_log,
            )
            if best_score > previous_best_score:
                stagnation_count = 0
            else:
                stagnation_count += 1

            is_valid = validation_log["verdict"] == "valid"
            has_valid_candidate = has_valid_candidate or is_valid
            if is_valid and refinement_config.early_exit_on_valid:
                early_exit_triggered = iteration < max_iterations
                break
            if (
                not has_valid_candidate
                and refinement_config.early_exit_on_plateau
                and iteration < max_iterations
                and stagnation_count >= plateau_patience
            ):
                early_exit_triggered = True
                break

            previous_candidate = sanitized_candidate
            previous_validation_log = validation_log

        final_status = _resolve_refinement_final_status(
            has_valid_candidate=has_valid_candidate,
            best_candidate=best_candidate,
        )
        reasoning_payload = _maybe_generate_reasoning(
            current_reasoning=None,
            include_reasoning=include_reasoning,
            reasoning_service=self.reasoning_service,
            input_json=input_json,
            output_json=best_candidate,
            file_name=file_name,
            document_type=document_type,
        )

        return {
            "raw_json": first_candidate,
            "validated_json": best_candidate,
            "output_json": best_candidate,
            "validation_log": best_log,
            "reasoning": reasoning_payload if include_reasoning else None,
            "refinement_meta": {
                "iterations_run": iterations_run,
                "max_iterations": max_iterations,
                "early_exit_triggered": early_exit_triggered,
                "final_status": final_status,
            },
        }
