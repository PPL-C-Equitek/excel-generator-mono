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
from llm.services.refinement_quality_rules import (
    RefinementQualityValidator,
    SummaryTotalItemsRule,
    TableHeaderOverlapRule,
    TableRowsNotEmptyRule,
)
from llm.services.refinement_stop_policies import (
    CompositeRefinementStopPolicy,
    ExitOnValidStopPolicy,
    PlateauStopPolicy,
    RefinementIterationState,
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


def _collect_refinement_quality_errors(
    output_json: Any,
    input_json: Any | None,
) -> list[dict[str, str]]:
    validator = RefinementQualityValidator(
        rules=[
            TableRowsNotEmptyRule(),
            TableHeaderOverlapRule(),
            SummaryTotalItemsRule(),
        ]
    )
    return validator.validate(output_json=output_json, input_json=input_json)


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
        if not isinstance(path, str) or not path.strip():
            continue
        if not isinstance(message, str) or not message.strip():
            continue
        if not isinstance(severity, str) or not severity.strip():
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
        stop_policy = CompositeRefinementStopPolicy(
            policies=[
                ExitOnValidStopPolicy(enabled=refinement_config.early_exit_on_valid),
                PlateauStopPolicy(enabled=refinement_config.early_exit_on_plateau),
            ]
        )

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
            stop_decision = stop_policy.should_stop(
                RefinementIterationState(
                    iteration=iteration,
                    max_iterations=max_iterations,
                    is_valid=is_valid,
                    has_valid_candidate=has_valid_candidate,
                    stagnation_count=stagnation_count,
                    plateau_patience=plateau_patience,
                )
            )
            if stop_decision.should_stop:
                early_exit_triggered = iteration < max_iterations
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
