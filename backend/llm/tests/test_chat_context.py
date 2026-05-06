import json
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from llm.prompts.extraction import (
    _build_chat_context_section,
    build_extraction_prompt,
)
from llm.services.generation_service import LlmGenerationService


class BuildChatContextSectionTest(SimpleTestCase):
    def test_positive_returns_section_with_chat_context_header(self):
        result = _build_chat_context_section("Format kolom tanggal DD/MM/YYYY")

        self.assertIn("## CHAT_CONTEXT", result)
        self.assertIn("Format kolom tanggal DD/MM/YYYY", result)

    def test_positive_instructs_ai_to_apply_strictly(self):
        result = _build_chat_context_section("Gunakan nama kolom Bahasa Indonesia")

        self.assertIn("Apply these instructions strictly", result)
        self.assertIn("take priority over default behavior", result)

    def test_positive_multiline_context_preserved(self):
        ctx = "USER: Tanggal DD/MM/YYYY\nASSISTANT: Siap\nUSER: Gunakan Bahasa Indonesia"
        result = _build_chat_context_section(ctx)

        self.assertIn("USER: Tanggal DD/MM/YYYY", result)
        self.assertIn("ASSISTANT: Siap", result)
        self.assertIn("USER: Gunakan Bahasa Indonesia", result)

    def test_negative_returns_none_for_none_input(self):
        self.assertIsNone(_build_chat_context_section(None))

    def test_negative_returns_none_for_empty_string(self):
        self.assertIsNone(_build_chat_context_section(""))

    def test_negative_returns_none_for_whitespace_only(self):
        self.assertIsNone(_build_chat_context_section("   \n\t  "))

    def test_edge_non_string_input_returns_none(self):
        self.assertIsNone(_build_chat_context_section(123))
        self.assertIsNone(_build_chat_context_section([]))


class BuildExtractionPromptWithChatContextTest(SimpleTestCase):
    def test_positive_includes_chat_context_section_when_provided(self):
        prompt = build_extraction_prompt(chat_context="Format tanggal DD/MM/YYYY")

        self.assertIn("## CHAT_CONTEXT", prompt)
        self.assertIn("Format tanggal DD/MM/YYYY", prompt)

    def test_positive_chat_context_section_appended_after_base_prompt(self):
        prompt = build_extraction_prompt(chat_context="Instruksi revisi")

        base_end = prompt.find("## CHAT_CONTEXT")
        self.assertGreater(base_end, 0, "## CHAT_CONTEXT harus ada setelah base prompt")

    def test_positive_both_schema_hint_and_chat_context_can_coexist(self):
        prompt = build_extraction_prompt(
            schema_hint="headers: [item, qty]",
            chat_context="Gunakan Bahasa Indonesia",
        )

        self.assertIn("## SCHEMA_HINT", prompt)
        self.assertIn("## CHAT_CONTEXT", prompt)
        self.assertIn("item", prompt)
        self.assertIn("Gunakan Bahasa Indonesia", prompt)

    def test_positive_schema_hint_appears_before_chat_context(self):
        prompt = build_extraction_prompt(
            schema_hint="headers: [item]",
            chat_context="Instruksi",
        )

        self.assertLess(prompt.find("## SCHEMA_HINT"), prompt.find("## CHAT_CONTEXT"))

    def test_negative_no_chat_context_section_when_not_provided(self):
        prompt = build_extraction_prompt()

        self.assertNotIn("## CHAT_CONTEXT", prompt)

    def test_negative_no_chat_context_section_for_empty_string(self):
        prompt = build_extraction_prompt(chat_context="")

        self.assertNotIn("## CHAT_CONTEXT", prompt)

    def test_negative_no_chat_context_section_for_whitespace(self):
        prompt = build_extraction_prompt(chat_context="   ")

        self.assertNotIn("## CHAT_CONTEXT", prompt)

    def test_negative_base_prompt_unchanged_when_no_chat_context(self):
        prompt_default = build_extraction_prompt()
        prompt_with_none = build_extraction_prompt(chat_context=None)

        self.assertEqual(prompt_default, prompt_with_none)

    def test_edge_chat_context_does_not_override_output_format_schema(self):
        prompt = build_extraction_prompt(chat_context="Ubah semua header menjadi bebas")

        self.assertIn("## OUTPUT_FORMAT", prompt)
        self.assertIn('"document_info"', prompt)
        self.assertIn('"content_data"', prompt)


class LlmGenerationServiceChatContextTest(SimpleTestCase):
    def _make_service(self, generate_return_value=None):
        mock_provider = Mock()
        mock_provider.generate_text.return_value = (
            generate_return_value or '{"headers":["A"],"rows":[["1"]]}'
        )
        mock_schema_source = Mock()
        mock_schema_source.get_prompt_fragment.return_value = "schema: [A]"

        service = LlmGenerationService(
            json_generator=Mock(),
            schema_prompt_source=mock_schema_source,
        )
        service.json_generator.generate.return_value = {"headers": ["A"], "rows": [["1"]]}
        return service, mock_schema_source

    def test_positive_chat_context_included_in_system_prompt(self):
        service, _ = self._make_service()
        chat_ctx = "USER: Gunakan Bahasa Indonesia\nASSISTANT: Siap"

        with patch("llm.services.generation_service.build_extraction_prompt") as mock_prompt:
            mock_prompt.return_value = "mocked_prompt"
            service.generate(input_json={"x": 1}, chat_context=chat_ctx)

        mock_prompt.assert_called_once_with(
            schema_hint=None,
            chat_context=chat_ctx,
        )

    def test_positive_no_chat_context_passes_none_to_prompt(self):
        service, _ = self._make_service()

        with patch("llm.services.generation_service.build_extraction_prompt") as mock_prompt:
            mock_prompt.return_value = "mocked_prompt"
            service.generate(input_json={"x": 1})

        mock_prompt.assert_called_once_with(
            schema_hint=None,
            chat_context=None,
        )

    def test_positive_chat_context_passed_alongside_custom_schema(self):
        service, mock_schema_source = self._make_service()

        with patch("llm.services.generation_service.build_extraction_prompt") as mock_prompt:
            mock_prompt.return_value = "mocked_prompt"
            service.generate(
                input_json={"x": 1},
                custom_schema_id="schema-123",
                chat_context="Format tanggal DD/MM/YYYY",
            )

        mock_prompt.assert_called_once_with(
            schema_hint="schema: [A]",
            chat_context="Format tanggal DD/MM/YYYY",
        )

    def test_negative_generate_still_works_without_chat_context(self):
        service, _ = self._make_service()
        result = service.generate(input_json={"x": 1})

        self.assertEqual(result, {"headers": ["A"], "rows": [["1"]]})

    def test_edge_empty_string_chat_context_passed_through(self):
        service, _ = self._make_service()

        with patch("llm.services.generation_service.build_extraction_prompt") as mock_prompt:
            mock_prompt.return_value = "mocked_prompt"
            service.generate(input_json={"x": 1}, chat_context="")

        mock_prompt.assert_called_once_with(schema_hint=None, chat_context="")


class BuildChatContextFromSessionTest(SimpleTestCase):
    def _make_message(self, role, content):
        msg = SimpleNamespace()
        msg.role = role
        msg.content = content
        return msg

    def _make_session(self, messages):
        session = Mock()
        user_msgs = [m for m in messages if getattr(m, "role", None) == "user"]
        session.messages.filter.return_value.order_by.return_value = list(reversed(user_msgs))
        return session

    def test_positive_formats_user_message_as_USER_prefix(self):
        from llm.services.chat_context_service import _build_chat_context_from_session

        session = self._make_session([
            self._make_message("user", "Format tanggal DD/MM/YYYY"),
        ])
        result = _build_chat_context_from_session(session)

        self.assertIn("USER: Format tanggal DD/MM/YYYY", result)

    def test_negative_excludes_assistant_only_messages(self):
        from llm.services.chat_context_service import _build_chat_context_from_session

        session = self._make_session([
            self._make_message("assistant", "Siap, akan diformat"),
        ])
        result = _build_chat_context_from_session(session)

        self.assertIsNone(result)

    def test_positive_multiple_messages_only_includes_user_lines(self):
        from llm.services.chat_context_service import _build_chat_context_from_session

        session = self._make_session([
            self._make_message("user", "Instruksi 1"),
            self._make_message("assistant", "Baik"),
            self._make_message("user", "Instruksi 2"),
        ])
        result = _build_chat_context_from_session(session)

        lines = result.split("\n")
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[0], "USER: Instruksi 1")
        self.assertEqual(lines[1], "USER: Instruksi 2")

    def test_edge_limits_to_last_n_user_instructions(self):
        from django.test import override_settings
        from llm.services.chat_context_service import _build_chat_context_from_session

        session = self._make_session([
            self._make_message("user", "Instruksi lama 1"),
            self._make_message("user", "Instruksi lama 2"),
            self._make_message("user", "Instruksi lama 3"),
            self._make_message("user", "Instruksi terbaru 1"),
            self._make_message("user", "Instruksi terbaru 2"),
        ])
        with override_settings(CHAT_CONTEXT_MAX_USER_INSTRUCTIONS=2):
            result = _build_chat_context_from_session(session)

        lines = result.split("\n")
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[0], "USER: Instruksi terbaru 1")
        self.assertEqual(lines[1], "USER: Instruksi terbaru 2")

    def test_negative_returns_none_when_session_is_none(self):
        from llm.services.chat_context_service import _build_chat_context_from_session

        self.assertIsNone(_build_chat_context_from_session(None))

    def test_negative_returns_none_when_session_has_no_messages(self):
        from llm.services.chat_context_service import _build_chat_context_from_session

        session = self._make_session([])
        self.assertIsNone(_build_chat_context_from_session(session))

    def test_edge_single_message_returns_single_line(self):
        from llm.services.chat_context_service import _build_chat_context_from_session

        session = self._make_session([
            self._make_message("user", "Satu instruksi"),
        ])
        result = _build_chat_context_from_session(session)

        self.assertNotIn("\n", result)
        self.assertEqual(result, "USER: Satu instruksi")

    def test_edge_clamps_zero_max_instructions_to_one_message(self):
        from django.test import override_settings
        from llm.services.chat_context_service import _build_chat_context_from_session

        session = self._make_session([
            self._make_message("user", "Instruksi 1"),
            self._make_message("user", "Instruksi 2"),
            self._make_message("user", "Instruksi 3"),
        ])
        with override_settings(CHAT_CONTEXT_MAX_USER_INSTRUCTIONS=0):
            result = _build_chat_context_from_session(session)

        lines = result.split("\n")
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0], "USER: Instruksi 3")


class InjectFileContextTest(SimpleTestCase):
    def _make_output(self, export_output_json):
        output = Mock()
        output.export_output_json = export_output_json
        return output

    def _make_session(self, last_output=None):
        session = Mock()
        session.generated_outputs.order_by.return_value.first.return_value = last_output
        return session

    def test_positive_prepends_system_message_with_file_context(self):
        from llm.services.chat_context_service import _inject_file_context_if_available

        export_json = {
            "document_info": {"source_type": "Excel", "filename": "data.xlsx"},
            "summary": {"total_tables": 1},
            "content_data": [{"table_name": "Sheet1", "headers": ["A"], "rows": []}],
        }
        session = self._make_session(last_output=self._make_output(export_json))
        history = [{"role": "user", "content": "Pertanyaan"}]

        result = _inject_file_context_if_available(session, history)

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["role"], "system")
        self.assertIn("[CONVERTED_FILE_CONTEXT]", result[0]["content"])
        self.assertIn("data.xlsx", result[0]["content"])

    def test_positive_reads_from_export_output_json_not_output_json(self):
        from llm.services.chat_context_service import _inject_file_context_if_available

        output = Mock()
        output.export_output_json = {
            "document_info": {"source_type": "Excel", "filename": "correct.xlsx"},
            "summary": {},
            "content_data": [],
        }
        output.output_json = {"headers": ["wrong"], "rows": []}
        session = self._make_session(last_output=output)

        result = _inject_file_context_if_available(session, [])

        self.assertIn("correct.xlsx", result[0]["content"])
        self.assertNotIn("wrong", result[0]["content"])

    def test_positive_original_history_preserved_after_system_message(self):
        from llm.services.chat_context_service import _inject_file_context_if_available

        session = self._make_session(last_output=self._make_output({"doc": "info"}))
        history = [
            {"role": "user", "content": "Pesan 1"},
            {"role": "assistant", "content": "Balasan"},
        ]

        result = _inject_file_context_if_available(session, history)

        self.assertEqual(result[1], history[0])
        self.assertEqual(result[2], history[1])

    def test_negative_returns_history_unchanged_when_session_is_none(self):
        from llm.services.chat_context_service import _inject_file_context_if_available

        history = [{"role": "user", "content": "Halo"}]
        result = _inject_file_context_if_available(None, history)

        self.assertEqual(result, history)

    def test_negative_returns_history_unchanged_when_no_generated_output(self):
        from llm.services.chat_context_service import _inject_file_context_if_available

        session = self._make_session(last_output=None)
        history = [{"role": "user", "content": "Halo"}]

        result = _inject_file_context_if_available(session, history)

        self.assertEqual(result, history)

    def test_edge_empty_history_still_gets_system_message_prepended(self):
        from llm.services.chat_context_service import _inject_file_context_if_available

        session = self._make_session(last_output=self._make_output({"some": "data"}))
        result = _inject_file_context_if_available(session, [])

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["role"], "system")

    def test_positive_compact_context_shows_metadata_headers_and_sample_rows(self):
        from llm.services.chat_context_service import _inject_file_context_if_available

        export_json = {
            "document_info": {"source_type": "Excel", "filename": "laporan.xlsx"},
            "summary": {"total_tables": 1, "total_rows": 2},
            "content_data": [
                {
                    "table_name": "Sheet1",
                    "headers": ["Nama", "Nilai"],
                    "rows": [
                        {"Nama": "Alice", "Nilai": 90},
                        {"Nama": "Bob", "Nilai": 80},
                    ],
                }
            ],
        }
        session = self._make_session(last_output=self._make_output(export_json))
        result = _inject_file_context_if_available(session, [])

        content = result[0]["content"]
        self.assertIn("laporan.xlsx", content)
        self.assertIn("Sheet1", content)
        self.assertIn("Nama", content)
        self.assertIn("Alice", content)
        self.assertNotIn('"rows"', content)

    def test_positive_fallback_builds_context_from_output_json_when_export_empty(self):
        from llm.services.chat_context_service import _inject_file_context_if_available

        output = Mock()
        output.export_output_json = {}
        output.output_json = {
            "headers": ["Unit", "Nilai"],
            "rows": [["ICU", 100]],
        }
        session = self._make_session(last_output=output)

        result = _inject_file_context_if_available(session, [])

        self.assertEqual(result[0]["role"], "system")
        self.assertIn("[CONVERTED_FILE_CONTEXT]", result[0]["content"])
        self.assertIn("Unit", result[0]["content"])

    def test_negative_returns_history_unchanged_when_both_export_and_output_json_empty(self):
        from llm.services.chat_context_service import _inject_file_context_if_available

        output = Mock()
        output.export_output_json = {}
        output.output_json = None
        session = self._make_session(last_output=output)
        history = [{"role": "user", "content": "Halo"}]

        result = _inject_file_context_if_available(session, history)

        self.assertEqual(result, history)


class BuildContentDataFromOutputContentDataTest(SimpleTestCase):
    def test_positive_uses_content_data_directly_when_llm_returns_export_format(self):
        from llm.services.export_service import _build_content_data_from_output

        content_data = [
            {"table_name": "Sheet1", "headers": ["Nama", "Nilai"], "rows": []}
        ]
        output_json = {
            "document_info": {"source_type": "Excel", "filename": "f.xlsx"},
            "summary": {"total_tables": 1},
            "content_data": content_data,
        }

        result = _build_content_data_from_output(output_json)

        self.assertEqual(result, content_data)

    def test_positive_export_format_not_treated_as_heuristic_flat_table(self):
        from llm.services.export_service import _build_content_data_from_output

        output_json = {
            "document_info": {"source_type": "Excel"},
            "summary": {},
            "content_data": [{"table_name": "T", "headers": ["A"], "rows": []}],
        }

        result = _build_content_data_from_output(output_json)

        headers = result[0]["headers"]
        self.assertNotIn("document_info", headers)
        self.assertNotIn("summary", headers)
        self.assertNotIn("content_data", headers)

    def test_positive_still_handles_simple_headers_rows_format(self):
        from llm.services.export_service import _build_content_data_from_output

        output_json = {"headers": ["A", "B"], "rows": [["x", "y"]]}
        result = _build_content_data_from_output(output_json)

        self.assertEqual(len(result), 1)
        self.assertIn("A", result[0]["headers"])
        self.assertIn("B", result[0]["headers"])

    def test_negative_empty_content_data_list_falls_through_to_heuristic(self):
        from llm.services.export_service import _build_content_data_from_output
        output_json = {
            "document_info": {},
            "content_data": [],
        }
        result = _build_content_data_from_output(output_json)

        self.assertIsInstance(result, list)

    def test_negative_non_list_content_data_falls_through_to_heuristic(self):
        from llm.services.export_service import _build_content_data_from_output

        output_json = {"content_data": "invalid"}
        result = _build_content_data_from_output(output_json)
        self.assertIsInstance(result, list)

    def test_edge_multiple_tables_in_content_data_all_returned(self):
        from llm.services.export_service import _build_content_data_from_output

        content_data = [
            {"table_name": "T1", "headers": ["X"], "rows": []},
            {"table_name": "T2", "headers": ["Y"], "rows": []},
        ]
        output_json = {"content_data": content_data, "document_info": {}, "summary": {}}
        result = _build_content_data_from_output(output_json)

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["table_name"], "T1")
        self.assertEqual(result[1]["table_name"], "T2")

class NormalizeSessionOutputExportPayloadTest(SimpleTestCase):
    def _make_output(self, export_output_json=None, output_json=None):
        obj = SimpleNamespace()
        obj.export_output_json = export_output_json
        obj.output_json = output_json
        return obj

    def _get_fn(self):
        import importlib
        mod = importlib.import_module("api.views")
        return mod._normalize_session_output_export_payload

    def test_positive_reads_export_output_json_not_raw_output_json(self):
        _normalize_session_output_export_payload = self._get_fn()

        output = self._make_output(
            export_output_json={
                "document_info": {"source_type": "Excel", "filename": "data.xlsx"},
                "summary": {"total_tables": 1},
                "content_data": [{"table_name": "T", "headers": ["A"], "rows": []}],
            },
            output_json={"headers": ["wrong"], "rows": []},
        )

        result = _normalize_session_output_export_payload(output)

        self.assertIn("document_info", result)
        self.assertIn("content_data", result)
        self.assertNotIn("headers", result)

    def test_positive_source_type_excel_passes_through_unchanged(self):
        _normalize_session_output_export_payload = self._get_fn()

        output = self._make_output(export_output_json={
            "document_info": {"source_type": "Excel", "filename": "report.xlsx"},
            "summary": {},
            "content_data": [],
        })
        result = _normalize_session_output_export_payload(output)

        self.assertEqual(result["document_info"]["source_type"], "Excel")

    def test_positive_source_type_pdf_passes_through_unchanged(self):
        _normalize_session_output_export_payload = self._get_fn()

        output = self._make_output(export_output_json={
            "document_info": {"source_type": "PDF", "filename": "doc.pdf"},
            "summary": {},
            "content_data": [],
        })
        result = _normalize_session_output_export_payload(output)

        self.assertEqual(result["document_info"]["source_type"], "PDF")

    def test_positive_pdf_filename_infers_source_type_pdf(self):
        _normalize_session_output_export_payload = self._get_fn()

        output = self._make_output(export_output_json={
            "document_info": {"filename": "invoice.pdf"},
            "summary": {},
            "content_data": [],
        })
        result = _normalize_session_output_export_payload(output)

        self.assertEqual(result["document_info"]["source_type"], "PDF")

    def test_positive_non_pdf_filename_infers_source_type_excel(self):
        _normalize_session_output_export_payload = self._get_fn()

        output = self._make_output(export_output_json={
            "document_info": {"filename": "data.xlsx"},
            "summary": {},
            "content_data": [],
        })
        result = _normalize_session_output_export_payload(output)

        self.assertEqual(result["document_info"]["source_type"], "Excel")

    def test_negative_empty_export_output_json_returns_empty_dict(self):
        _normalize_session_output_export_payload = self._get_fn()

        output = self._make_output(export_output_json={})
        result = _normalize_session_output_export_payload(output)

        self.assertEqual(result, {})

    def test_negative_none_export_output_json_returns_empty_dict(self):
        _normalize_session_output_export_payload = self._get_fn()

        output = self._make_output(export_output_json=None)
        result = _normalize_session_output_export_payload(output)

        self.assertEqual(result, {})

    def test_negative_missing_document_info_returns_payload_as_is(self):
        _normalize_session_output_export_payload = self._get_fn()

        payload = {"summary": {}, "content_data": []}
        output = self._make_output(export_output_json=payload)
        result = _normalize_session_output_export_payload(output)

        self.assertNotIn("document_info", result)

    def test_edge_does_not_mutate_original_export_output_json(self):
        _normalize_session_output_export_payload = self._get_fn()

        original = {
            "document_info": {"filename": "data.xlsx"},
            "content_data": [],
        }
        output = self._make_output(export_output_json=original)
        _normalize_session_output_export_payload(output)

        self.assertNotIn("source_type", original["document_info"])


class BuildTableContextLinesTest(SimpleTestCase):
    def test_positive_returns_summary_line_with_column_and_row_count(self):
        from llm.services.chat_context_service import _build_table_context_lines

        table = {"table_name": "Sales", "headers": ["A", "B"], "rows": [{"A": 1, "B": 2}]}
        lines = _build_table_context_lines(table)

        self.assertEqual(lines[0], "Table 'Sales': 2 columns, 1 rows")

    def test_positive_includes_headers_line_when_headers_present(self):
        from llm.services.chat_context_service import _build_table_context_lines

        table = {"table_name": "T", "headers": ["Col1", "Col2"], "rows": []}
        lines = _build_table_context_lines(table)

        self.assertTrue(any("Col1" in line and "Col2" in line for line in lines))

    def test_negative_no_headers_line_when_empty_headers(self):
        from llm.services.chat_context_service import _build_table_context_lines

        table = {"table_name": "T", "headers": [], "rows": []}
        lines = _build_table_context_lines(table)

        self.assertFalse(any("Headers:" in line for line in lines))

    def test_positive_includes_up_to_3_sample_rows(self):
        from llm.services.chat_context_service import _build_table_context_lines

        rows = [{"X": i} for i in range(3)]
        table = {"table_name": "T", "headers": ["X"], "rows": rows}
        lines = _build_table_context_lines(table)

        row_lines = [line for line in lines if line.startswith("  Row")]
        self.assertEqual(len(row_lines), 3)

    def test_edge_truncates_to_3_rows_when_more_exist(self):
        from llm.services.chat_context_service import _build_table_context_lines

        rows = [{"X": i} for i in range(5)]
        table = {"table_name": "T", "headers": ["X"], "rows": rows}
        lines = _build_table_context_lines(table)

        row_lines = [line for line in lines if line.startswith("  Row")]
        self.assertEqual(len(row_lines), 3)

    def test_edge_truncates_to_5_columns_per_row_when_more_exist(self):
        from llm.services.chat_context_service import _build_table_context_lines

        row = {f"col{i}": i for i in range(8)}
        table = {"table_name": "T", "headers": [f"col{i}" for i in range(8)], "rows": [row]}
        lines = _build_table_context_lines(table)

        row_line = next(line for line in lines if line.startswith("  Row"))
        parsed = json.loads(row_line.split(": ", 1)[1])
        self.assertEqual(len(parsed), 5)

    def test_edge_non_dict_rows_skipped(self):
        from llm.services.chat_context_service import _build_table_context_lines

        table = {"table_name": "T", "headers": ["A"], "rows": [["list_row"], "string_row"]}
        lines = _build_table_context_lines(table)

        row_lines = [line for line in lines if line.startswith("  Row")]
        self.assertEqual(len(row_lines), 0)

    def test_edge_uses_default_sheet_name_when_table_name_missing(self):
        from llm.services.chat_context_service import _build_table_context_lines

        table = {"headers": ["A"], "rows": []}
        lines = _build_table_context_lines(table)

        self.assertIn("Sheet", lines[0])


class BuildCompactFileContextTest(SimpleTestCase):
    def test_positive_starts_with_converted_file_context_header(self):
        from llm.services.chat_context_service import _build_compact_file_context

        result = _build_compact_file_context({})

        self.assertTrue(result.startswith("[CONVERTED_FILE_CONTEXT]"))

    def test_positive_includes_file_info_from_document_info(self):
        from llm.services.chat_context_service import _build_compact_file_context

        export_json = {"document_info": {"filename": "report.xlsx", "source_type": "Excel"}}
        result = _build_compact_file_context(export_json)

        self.assertIn("report.xlsx", result)
        self.assertIn("Excel", result)

    def test_positive_includes_summary_key_value_pairs(self):
        from llm.services.chat_context_service import _build_compact_file_context

        export_json = {"summary": {"total_tables": 2, "total_rows": 10}}
        result = _build_compact_file_context(export_json)

        self.assertIn("total_tables=2", result)
        self.assertIn("total_rows=10", result)

    def test_negative_no_file_line_when_document_info_missing(self):
        from llm.services.chat_context_service import _build_compact_file_context

        result = _build_compact_file_context({})

        self.assertNotIn("File:", result)

    def test_negative_no_summary_line_when_summary_is_empty_dict(self):
        from llm.services.chat_context_service import _build_compact_file_context

        export_json = {"summary": {}}
        result = _build_compact_file_context(export_json)

        self.assertNotIn("Summary:", result)

    def test_negative_non_dict_tables_in_content_data_are_skipped(self):
        from llm.services.chat_context_service import _build_compact_file_context

        export_json = {"content_data": ["not_a_dict", 42, None]}
        result = _build_compact_file_context(export_json)

        self.assertNotIn("Table '", result)

    def test_negative_no_table_lines_when_content_data_absent(self):
        from llm.services.chat_context_service import _build_compact_file_context

        result = _build_compact_file_context({"document_info": {"filename": "f.csv"}})

        self.assertNotIn("Table '", result)

    def test_positive_includes_table_name_from_content_data(self):
        from llm.services.chat_context_service import _build_compact_file_context

        export_json = {
            "content_data": [{"table_name": "DataSheet", "headers": [], "rows": []}]
        }
        result = _build_compact_file_context(export_json)

        self.assertIn("DataSheet", result)
