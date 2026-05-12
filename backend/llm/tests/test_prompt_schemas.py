from django.test import SimpleTestCase

from llm.prompts.schemas import (
    MAX_REASONING_KEY_SAMPLE,
    MAX_REASONING_TABLES,
    _build_reasoning_context_summary,
    _summarize_extracted_payload,
    _summarize_generic_payload,
    _summarize_row_shape,
    _summarize_scalar_object,
    _summarize_table,
    _summarize_tabular_payload,
    _summarize_upload_wrapper,
    _to_json_context,
    _truncate_text,
    build_conversion_reasoning_prompt,
)


class PromptSchemasTest(SimpleTestCase):
    def test_truncate_text_handles_non_string_blank_and_long_values(self):
        self.assertIsNone(_truncate_text(123))
        self.assertIsNone(_truncate_text("   "))
        self.assertEqual(_truncate_text("  ok  "), "ok")
        self.assertEqual(
            _truncate_text("abcdef", max_chars=4),
            "abcd... [TRUNCATED]",
        )

    def test_summarize_row_shape_covers_dict_list_and_scalar(self):
        object_shape = _summarize_row_shape({"name": "A", "amount": 10})
        array_shape = _summarize_row_shape(["A", 10])
        scalar_shape = _summarize_row_shape(99)

        self.assertEqual(object_shape["row_type"], "object")
        self.assertEqual(object_shape["key_count"], 2)
        self.assertEqual(array_shape, {"row_type": "array", "column_count": 2})
        self.assertEqual(scalar_shape, {"row_type": "int"})

    def test_summarize_table_uses_fallback_name_and_includes_first_row_shape(self):
        summary = _summarize_table(
            {
                "table_name": "   ",
                "headers": ["item", "qty"],
                "rows": [{"item": "Pen", "qty": 2}],
            },
            fallback_name="FallbackTable",
        )

        self.assertEqual(summary["table_name"], "FallbackTable")
        self.assertEqual(summary["header_count"], 2)
        self.assertEqual(summary["row_count"], 1)
        self.assertEqual(summary["first_row_shape"]["row_type"], "object")

    def test_summarize_scalar_object_handles_invalid_empty_and_max_sample(self):
        self.assertIsNone(_summarize_scalar_object(["not-an-object"]))
        self.assertIsNone(_summarize_scalar_object({"nested": {"a": 1}}))

        payload = {f"k{i}": i for i in range(MAX_REASONING_KEY_SAMPLE + 5)}
        summarized = _summarize_scalar_object(payload)

        self.assertIsNotNone(summarized)
        self.assertEqual(len(summarized), MAX_REASONING_KEY_SAMPLE)
        self.assertIn("k0", summarized)
        self.assertNotIn(f"k{MAX_REASONING_KEY_SAMPLE + 1}", summarized)

    def test_summarize_tabular_payload_returns_none_for_non_tabular_values(self):
        self.assertIsNone(_summarize_tabular_payload(["not-an-object"]))
        self.assertIsNone(_summarize_tabular_payload({"content_data": "not-a-list"}))

    def test_summarize_tabular_payload_handles_non_dict_items_and_omitted_tables(self):
        content_data = ["invalid-entry"]
        for index in range(MAX_REASONING_TABLES + 2):
            content_data.append(
                {
                    "table_name": f"Table {index}",
                    "headers": ["col1"],
                    "rows": [{"col1": index}],
                }
            )

        summary = _summarize_tabular_payload(
            {
                "document_info": {"filename": "report.xlsx", "source_type": "Excel"},
                "summary": {"total_tables": len(content_data), "meta": {"ignored": True}},
                "content_data": content_data,
            }
        )

        self.assertIsNotNone(summary)
        self.assertEqual(summary["kind"], "tabular_output")
        self.assertEqual(summary["table_count"], len(content_data))
        self.assertEqual(len(summary["tables"]), MAX_REASONING_TABLES - 1)
        self.assertEqual(
            summary["tables_omitted"],
            len(content_data) - MAX_REASONING_TABLES,
        )
        self.assertEqual(summary["document_info"]["filename"], "report.xlsx")
        self.assertEqual(summary["summary"]["total_tables"], len(content_data))

    def test_summarize_extracted_payload_handles_dict_list_and_scalar(self):
        extracted_dict = {
            **{f"Sheet{i}": [{"col": i}] for i in range(MAX_REASONING_TABLES + 1)},
            "SheetX": "invalid-rows",
        }
        summarized_dict = _summarize_extracted_payload(extracted_dict)
        summarized_list = _summarize_extracted_payload([{"row": 1}, {"row": 2}])
        summarized_scalar = _summarize_extracted_payload("raw-text")

        self.assertEqual(summarized_dict["sheet_count"], len(extracted_dict))
        self.assertIn("sheets_omitted", summarized_dict)
        self.assertEqual(summarized_list["item_count"], 2)
        self.assertEqual(summarized_list["first_item_shape"]["row_type"], "object")
        self.assertEqual(summarized_scalar, {"value_type": "str"})

    def test_summarize_upload_wrapper_includes_previous_output_summary(self):
        summary = _summarize_upload_wrapper(
            {
                "filename": "invoice.pdf",
                "format": "pdf",
                "user_prompt": "  keep paid invoices only  ",
                "extracted": {"Sheet1": [{"status": "paid"}]},
                "previous_output": {
                    "content_data": [
                        {"table_name": "Sheet1", "headers": ["status"], "rows": [{"status": "all"}]}
                    ]
                },
            }
        )

        self.assertEqual(summary["kind"], "upload_wrapper")
        self.assertTrue(summary["has_extracted"])
        self.assertTrue(summary["has_previous_output"])
        self.assertEqual(summary["filename"], "invoice.pdf")
        self.assertEqual(summary["format"], "pdf")
        self.assertEqual(summary["user_prompt"], "keep paid invoices only")
        self.assertEqual(summary["previous_output"]["kind"], "tabular_output")

    def test_summarize_generic_payload_covers_object_array_and_scalar(self):
        object_summary = _summarize_generic_payload({"a": 1, "b": "x"}, kind="input_context")
        array_summary = _summarize_generic_payload([1, "x", {"k": "v"}], kind="output_context")
        scalar_summary = _summarize_generic_payload(3.14, kind="input_context")

        self.assertEqual(object_summary["payload_type"], "object")
        self.assertEqual(array_summary["payload_type"], "array")
        self.assertEqual(array_summary["item_types"], ["int", "str", "dict"])
        self.assertEqual(scalar_summary["payload_type"], "float")

    def test_build_reasoning_context_summary_prefers_upload_then_tabular_then_generic(self):
        upload_summary = _build_reasoning_context_summary(
            {"extracted": {"Sheet1": []}},
            kind="input_context",
        )
        tabular_summary = _build_reasoning_context_summary(
            {"content_data": [{"table_name": "S1", "headers": ["a"], "rows": [{"a": 1}]}]},
            kind="output_context",
        )
        generic_summary = _build_reasoning_context_summary("plain-text", kind="input_context")

        self.assertEqual(upload_summary["kind"], "upload_wrapper")
        self.assertEqual(tabular_summary["kind"], "tabular_output")
        self.assertEqual(generic_summary["payload_type"], "str")

    def test_to_json_context_handles_truncation_and_non_serializable_values(self):
        class _NonSerializable:
            def __str__(self):
                return "non-serializable-value"

        self.assertEqual(_to_json_context({"a": 1}), '{"a": 1}')

        truncated = _to_json_context({"text": "x" * 30}, max_chars=15)
        self.assertTrue(truncated.endswith("... [TRUNCATED]"))

        fallback = _to_json_context(_NonSerializable())
        self.assertEqual(fallback, "non-serializable-value")

    def test_build_conversion_reasoning_prompt_includes_context_and_goal(self):
        prompt = build_conversion_reasoning_prompt(
            input_json={
                "filename": "invoice.pdf",
                "format": "pdf",
                "extracted": {"Sheet1": [{"item": "Pen", "qty": 2}]},
            },
            output_json={
                "document_info": {"source_type": "PDF", "filename": "invoice.pdf"},
                "summary": {"total_tables": 1},
                "content_data": [
                    {"table_name": "Sheet1", "headers": ["item", "qty"], "rows": [{"item": "Pen", "qty": 2}]}
                ],
            },
            file_name="invoice.pdf",
            document_type="pdf",
        )

        self.assertIn("file_name: invoice.pdf", prompt)
        self.assertIn("document_type: pdf", prompt)
        self.assertIn("INPUT_JSON:", prompt)
        self.assertIn("OUTPUT_JSON:", prompt)
        self.assertIn("Summarize confidence level in the conversion result.", prompt)
