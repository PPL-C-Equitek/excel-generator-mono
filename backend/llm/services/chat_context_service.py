"""
Chat Context Service

Handles building and injecting contextual information into LLM chat conversations.
This includes:
- Formatting user message history from a session as a chat context string
- Constructing a compact representation of an exported file for LLM context
- Injecting the file context as a system message into the chat history
"""

import json

from django.conf import settings

from chat_sessions.models import ChatMessage
from llm.services.export_service import build_export_output_json


_MAX_COMPACT_TABLES = 5
_MAX_COMPACT_HEADERS = 20


def _build_table_context_lines(table: dict) -> list:
    """Build a list of compact text lines describing a single table's metadata and sample rows."""
    table_name = table.get("table_name", "Sheet")
    headers = table.get("headers") or []
    rows = table.get("rows") or []
    lines = [f"Table '{table_name}': {len(headers)} columns, {len(rows)} rows"]
    if headers:
        shown = headers[:_MAX_COMPACT_HEADERS]
        header_str = ", ".join(str(h) for h in shown)
        if len(headers) > _MAX_COMPACT_HEADERS:
            header_str += f", +{len(headers) - _MAX_COMPACT_HEADERS} more"
        lines.append(f"  Headers: {header_str}")
    for i, row in enumerate(rows[:3]):
        if isinstance(row, dict):
            sample = dict(list(row.items())[:5])
            lines.append(f"  Row {i + 1}: {json.dumps(sample)}")
    return lines


def _build_compact_file_context(export_json: dict) -> str:
    """Build a compact plain-text summary of an export payload to inject into chat context."""
    lines = [
        "[CONVERTED_FILE_CONTEXT]",
        "The user is reviewing a converted file. "
        "Use the metadata and samples below to answer questions about the file.",
    ]
    doc_info = export_json.get("document_info")
    if isinstance(doc_info, dict):
        filename = doc_info.get("filename", "unknown")
        source_type = doc_info.get("source_type", "unknown")
        lines.append(f"File: {filename} ({source_type})")

    summary = export_json.get("summary")
    if isinstance(summary, dict) and summary:
        parts = [f"{k}={v}" for k, v in summary.items()]
        lines.append("Summary: " + ", ".join(parts))

    content_data = export_json.get("content_data")
    if isinstance(content_data, list):
        tables = [t for t in content_data if isinstance(t, dict)]
        for table in tables[:_MAX_COMPACT_TABLES]:
            lines.extend(_build_table_context_lines(table))
        if len(tables) > _MAX_COMPACT_TABLES:
            lines.append(f"+{len(tables) - _MAX_COMPACT_TABLES} tables omitted")

    return "\n".join(lines)


def _inject_file_context_if_available(session, history: list) -> list:
    """
    Prepend a system message containing the converted file context to the chat history,
    if a generated output with export data is available for the session.
    Falls back to building from raw output_json if export_output_json is empty.
    Persists the fallback result back to GeneratedOutput (best-effort) to avoid
    recomputing on every subsequent chat request.
    """
    if session is None:
        return history
    last_output = session.generated_outputs.order_by("-created_at").first()
    if last_output is None:
        return history
    export_json = last_output.export_output_json
    if not isinstance(export_json, dict) or not export_json:
        raw = getattr(last_output, "output_json", None)
        if raw:
            export_json = build_export_output_json(input_json=raw, output_json=raw)
            try:
                last_output.export_output_json = export_json
                last_output.save(update_fields=["export_output_json"])
            except Exception:
                pass
    if not isinstance(export_json, dict) or not export_json:
        return history
    return [{"role": "system", "content": _build_compact_file_context(export_json)}] + history


def _build_chat_context_from_session(session) -> str | None:
    """
    Build a formatted string of the most recent user instructions from a session,
    to be injected as CHAT_CONTEXT into the LLM extraction prompt.
    Returns None if there are no user messages.
    """
    if session is None:
        return None
    max_instructions = max(1, getattr(settings, "CHAT_CONTEXT_MAX_USER_INSTRUCTIONS", 5))
    recent = list(
        session.messages
        .filter(role=ChatMessage.ROLE_USER)
        .order_by("-created_at")[:max_instructions]
    )
    if not recent:
        return None
    recent.reverse()
    return "\n".join(f"USER: {msg.content}" for msg in recent)
