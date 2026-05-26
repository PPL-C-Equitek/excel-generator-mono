from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


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


@dataclass(frozen=True)
class RefinementValidationContext:
    output_json: dict[str, Any]
    input_json: Any | None
    source_headers: set[str]
    total_rows: int


class RefinementQualityRule(Protocol):
    def evaluate(self, context: RefinementValidationContext) -> list[dict[str, str]]: ...


class TableRowsNotEmptyRule:
    def evaluate(self, context: RefinementValidationContext) -> list[dict[str, str]]:
        errors: list[dict[str, str]] = []
        content_data = context.output_json.get("content_data")
        if not isinstance(content_data, list):
            return errors

        for table_index, table in enumerate(content_data):
            if not isinstance(table, dict):
                continue
            rows = table.get("rows")
            if isinstance(rows, list) and len(rows) == 0:
                errors.append(
                    _build_quality_error(
                        f"$.content_data[{table_index}].rows",
                        "rows must not be empty for refinement quality checks.",
                    )
                )
        return errors


class TableHeaderOverlapRule:
    def evaluate(self, context: RefinementValidationContext) -> list[dict[str, str]]:
        errors: list[dict[str, str]] = []
        content_data = context.output_json.get("content_data")
        if not isinstance(content_data, list):
            return errors

        for table_index, table in enumerate(content_data):
            if not isinstance(table, dict):
                continue
            output_headers = _normalized_headers(table.get("headers"))
            has_overlap = bool(output_headers.intersection(context.source_headers))
            if context.source_headers and output_headers and not has_overlap:
                errors.append(
                    _build_quality_error(
                        f"$.content_data[{table_index}].headers",
                        (
                            "Output headers do not overlap with source-extracted headers, "
                            "which indicates likely semantic mismatch."
                        ),
                    )
                )
        return errors


class SummaryTotalItemsRule:
    def evaluate(self, context: RefinementValidationContext) -> list[dict[str, str]]:
        summary = context.output_json.get("summary")
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

        if total_items == context.total_rows:
            return []

        return [
            _build_quality_error(
                "$.summary.total_items",
                "summary.total_items does not match the number of rows in content_data.",
            )
        ]


class RefinementQualityValidator:
    def __init__(self, rules: list[RefinementQualityRule]):
        self._rules = list(rules)

    def validate(self, output_json: Any, input_json: Any | None = None) -> list[dict[str, str]]:
        if not isinstance(output_json, dict):
            return []

        content_data = output_json.get("content_data")
        if not isinstance(content_data, list):
            return []

        total_rows = 0
        for table in content_data:
            if not isinstance(table, dict):
                continue
            rows = table.get("rows")
            if isinstance(rows, list):
                total_rows += len(rows)

        context = RefinementValidationContext(
            output_json=output_json,
            input_json=input_json,
            source_headers=_collect_source_headers(input_json) if input_json is not None else set(),
            total_rows=total_rows,
        )

        errors: list[dict[str, str]] = []
        for rule in self._rules:
            errors.extend(rule.evaluate(context))
        return errors