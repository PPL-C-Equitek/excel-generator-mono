from django.test import SimpleTestCase
from unittest.mock import Mock
from unittest.mock import patch

from llm.services.refinement_service import (
    RefinementConfig,
    RefinementOrchestrator,
    _compact_validation_issues,
    _compact_validation_log_for_instruction,
    _extract_ocr_confidence,
    _collect_refinement_quality_errors,
    _collect_headers_from_header_list,
    _collect_headers_from_rows,
    _collect_nested_source_headers,
    _collect_source_headers,
    _normalized_headers,
    _resolve_refinement_final_status,
    build_refinement_instruction,
    build_validation_log,
    _sanitize_reasoning_meta_keys,
)
from file_processing.services.export_service import OutputLLMValidationError


class RefinementValidationLogTest(SimpleTestCase):
    def test_sanitize_reasoning_meta_keys_returns_non_dict_payload_unchanged(self):
        payload = ["a", "b"]

        self.assertEqual(_sanitize_reasoning_meta_keys(payload), payload)

    def test_build_validation_log_returns_structured_error_for_invalid_payload(self):
        log = build_validation_log(
            {
                "document_info": {"source_type": "Excel"},
                "summary": {"total_tables": 1},
                "content_data": [],
            },
            iteration=1,
        )

        self.assertEqual(log["verdict"], "invalid")
        self.assertEqual(log["iteration"], 1)
        self.assertTrue(log["errors"])
        self.assertEqual(log["errors"][0]["severity"], "error")
        self.assertIn("path", log["errors"][0])

    def test_build_validation_log_adds_warning_for_ambiguous_values(self):
        log = build_validation_log(
            {
                "document_info": {"source_type": "Excel", "filename": "unknown"},
                "summary": {"total_tables": 1},
                "content_data": [
                    {
                        "table_name": "Sheet1",
                        "headers": ["item"],
                        "rows": [{"item": "unknown"}],
                    }
                ],
            },
            iteration=1,
        )

        self.assertTrue(log["warnings"])
        self.assertEqual(log["warnings"][0]["severity"], "warning")

    def test_build_validation_log_adds_warning_for_null_payload_value(self):
        log = build_validation_log(
            {
                "document_info": {"source_type": "Excel", "filename": None},
                "summary": {"total_tables": 1},
                "content_data": [
                    {
                        "table_name": "Sheet1",
                        "headers": ["item"],
                        "rows": [{"item": "Pen"}],
                    }
                ],
            },
            iteration=1,
        )

        self.assertTrue(any("unresolved ambiguity" in issue["message"] for issue in log["warnings"]))

    def test_build_validation_log_marks_empty_rows_as_invalid_quality(self):
        log = build_validation_log(
            {
                "document_info": {"source_type": "PDF", "filename": "sample.pdf"},
                "summary": {"total_items": 0},
                "content_data": [
                    {
                        "table_name": "result",
                        "headers": ["No", "Rumah", "Luas"],
                        "rows": [],
                    }
                ],
            },
            iteration=1,
            input_json={
                "content_data": [
                    {
                        "headers": ["ID", "Barang", "Harga"],
                        "rows": [{"ID": "1", "Barang": "A", "Harga": 1000}],
                    }
                ]
            },
        )

        self.assertEqual(log["verdict"], "invalid")
        self.assertTrue(log["errors"])
        self.assertIn("quality checks", log["summary"].lower())

    def test_build_validation_log_marks_header_mismatch_as_invalid_quality(self):
        log = build_validation_log(
            {
                "document_info": {"source_type": "PDF", "filename": "sample.pdf"},
                "summary": {"total_items": 1},
                "content_data": [
                    {
                        "table_name": "result",
                        "headers": ["No", "Rumah", "Luas"],
                        "rows": [{"No": "1", "Rumah": "A", "Luas": "100"}],
                    }
                ],
            },
            iteration=1,
            input_json={
                "content_data": [
                    {
                        "headers": ["ID", "Barang", "Harga"],
                        "rows": [{"ID": "1", "Barang": "A", "Harga": 1000}],
                    }
                ]
            },
        )

        self.assertEqual(log["verdict"], "invalid")
        self.assertTrue(
            any("semantic mismatch" in issue["message"] for issue in log["errors"])
        )

    def test_build_validation_log_blocks_low_confidence_ocr_and_requests_manual_review(self):
        log = build_validation_log(
            {
                "document_info": {"source_type": "PDF", "filename": "sample.pdf"},
                "summary": {"total_items": 1},
                "content_data": [
                    {
                        "table_name": "result",
                        "headers": ["No", "Rumah", "Luas"],
                        "rows": [{"No": "1", "Rumah": "A", "Luas": "100"}],
                    }
                ],
            },
            iteration=1,
            input_json={
                "ocr_metadata": {"confidence_score": 52.0, "confidence_level": "low"},
                "content_data": [
                    {
                        "headers": ["ID", "Barang", "Harga"],
                        "rows": [{"ID": "1", "Barang": "A", "Harga": 1000}],
                    }
                ],
            },
        )

        self.assertEqual(log["verdict"], "invalid")
        # Expect a quality error about OCR confidence that requests manual review
        self.assertTrue(
            any(
                issue.get("path") == "$.ocr_metadata.confidence_score"
                and ("manual review" in issue.get("message", "").lower() or "low ocr" in issue.get("message", "").lower())
                for issue in log.get("errors", [])
            )
        )

    def test_build_validation_log_marks_total_items_mismatch_as_invalid_quality(self):
        log = build_validation_log(
            {
                "document_info": {"source_type": "PDF", "filename": "sample.pdf"},
                "summary": {"total_items": 2},
                "content_data": [
                    {
                        "table_name": "result",
                        "headers": ["ID", "Barang"],
                        "rows": [{"ID": "1", "Barang": "A"}],
                    }
                ],
            },
            iteration=1,
            input_json={
                "content_data": [
                    {
                        "headers": ["ID", "Barang"],
                        "rows": [{"ID": "1", "Barang": "A"}],
                    }
                ]
            },
        )

        self.assertEqual(log["verdict"], "invalid")
        self.assertTrue(
            any(
                issue["path"] == "$.summary.total_items"
                for issue in log["errors"]
            )
        )

    def test_build_validation_log_marks_negative_total_items_as_invalid_quality(self):
        log = build_validation_log(
            {
                "document_info": {"source_type": "PDF", "filename": "sample.pdf"},
                "summary": {"total_items": -1},
                "content_data": [
                    {
                        "table_name": "result",
                        "headers": ["ID", "Barang"],
                        "rows": [{"ID": "1", "Barang": "A"}],
                    }
                ],
            },
            iteration=1,
            input_json={
                "content_data": [
                    {
                        "headers": ["ID", "Barang"],
                        "rows": [{"ID": "1", "Barang": "A"}],
                    }
                ]
            },
        )

        self.assertEqual(log["verdict"], "invalid")
        self.assertTrue(
            any(
                issue["path"] == "$.summary.total_items"
                and "non-negative integer" in issue["message"]
                for issue in log["errors"]
            )
        )

    def test_build_refinement_instruction_truncates_large_payload(self):
        long_value = "a" * 13000
        instruction = build_refinement_instruction(
            previous_output_json={"value": long_value},
            validation_log={
                "iteration": 1,
                "verdict": "invalid",
                "errors": [{"path": "$.value", "message": "too long", "severity": "error"}],
                "warnings": [],
                "summary": "invalid",
            },
        )

        self.assertIn("PREVIOUS_OUTPUT_JSON:", instruction)
        self.assertIn("[TRUNCATED]", instruction)

    @patch("llm.services.refinement_service.validate_output_llm")
    def test_build_validation_log_uses_root_path_when_error_has_no_extractable_path(
        self,
        mock_validate_output_llm,
    ):
        mock_validate_output_llm.side_effect = OutputLLMValidationError("Generic schema failure")

        log = build_validation_log(
            {"document_info": {}, "summary": {}, "content_data": []},
            iteration=1,
        )

        self.assertEqual(log["errors"][0]["path"], "$")

    def test_build_refinement_instruction_falls_back_to_string_for_non_serializable_payload(self):
        class NonSerializable:
            def __str__(self):
                return "non-serializable-value"

        instruction = build_refinement_instruction(
            previous_output_json=NonSerializable(),
            validation_log={
                "iteration": 1,
                "verdict": "invalid",
                "errors": [],
                "warnings": [],
                "summary": "invalid",
            },
        )

        self.assertIn("non-serializable-value", instruction)

    def test_build_refinement_instruction_limits_embedded_validation_issues(self):
        validation_log = {
            "iteration": 2,
            "verdict": "invalid",
            "summary": "many issues",
            "errors": [
                {"path": f"$.errors[{index}]", "message": f"error-{index}", "severity": "error"}
                for index in range(20)
            ],
            "warnings": [
                {"path": f"$.warnings[{index}]", "message": f"warning-{index}", "severity": "warning"}
                for index in range(10)
            ],
        }

        instruction = build_refinement_instruction(
            previous_output_json={"value": "ok"},
            validation_log=validation_log,
        )

        self.assertIn('"error_count": 20', instruction)
        self.assertIn('"warning_count": 10', instruction)
        self.assertIn("error-11", instruction)
        self.assertNotIn("error-12", instruction)
        self.assertIn("warning-3", instruction)
        self.assertNotIn("warning-4", instruction)

    def test_build_validation_log_handles_non_dict_table_entries(self):
        log = build_validation_log(
            {
                "document_info": {"source_type": "PDF", "filename": "sample.pdf"},
                "summary": {"total_items": 0},
                "content_data": ["unexpected-item"],
            },
            iteration=1,
            input_json={"headers": ["id"]},
        )

        self.assertEqual(log["verdict"], "invalid")

    def test_build_validation_log_covers_source_header_and_summary_non_dict_branches(self):
        log = build_validation_log(
            {
                "document_info": {"source_type": "PDF", "filename": "sample.pdf"},
                "summary": "not-an-object",
                "content_data": [
                    {
                        "table_name": "result",
                        "headers": ["unrelated"],
                        "rows": "not-a-list",
                    }
                ],
            },
            iteration=1,
            input_json={
                "headers": [None, "   ", "ID"],
                "rows": ["not-dict", {1: "value"}, {"name": "A"}],
            },
        )

        self.assertEqual(log["iteration"], 1)
        self.assertEqual(log["verdict"], "invalid")


class RefinementHelpersTest(SimpleTestCase):
    def test_collect_refinement_quality_errors_returns_empty_for_non_dict_output(self):
        self.assertEqual(_collect_refinement_quality_errors("invalid", input_json={}), [])

    def test_collect_headers_from_header_list_returns_empty_for_non_list(self):
        self.assertEqual(_collect_headers_from_header_list("not-a-list"), set())

    def test_collect_headers_from_rows_returns_empty_for_non_list(self):
        self.assertEqual(_collect_headers_from_rows("not-a-list"), set())

    def test_collect_nested_source_headers_handles_dict_payload(self):
        headers = _collect_nested_source_headers(
            {
                "headers": ["ID"],
                "rows": [{"Name": "A"}],
            }
        )

        self.assertEqual(headers, {"id", "name"})

    def test_collect_source_headers_handles_non_dict_payload(self):
        headers = _collect_source_headers([{"headers": ["SKU"]}, {"rows": [{"Qty": 1}]}])

        self.assertEqual(headers, {"sku", "qty"})

    def test_normalized_headers_returns_empty_for_non_list(self):
        self.assertEqual(_normalized_headers("not-a-list"), set())

    def test_resolve_refinement_final_status_returns_failed_without_candidates(self):
        self.assertEqual(
            _resolve_refinement_final_status(has_valid_candidate=False, best_candidate=None),
            "failed",
        )

    def test_compact_validation_issues_returns_empty_for_non_list(self):
        self.assertEqual(_compact_validation_issues("not-a-list", max_items=5), [])

    def test_compact_validation_issues_skips_invalid_items_and_required_fields(self):
        issues = [
            "not-a-dict",
            {"path": "$.ok", "message": "", "severity": "error"},
            {"path": "$.ok", "message": "has message", "severity": None},
            {"path": "  $.valid.path  ", "message": "  valid message  ", "severity": "  warning  "},
        ]

        compacted = _compact_validation_issues(issues, max_items=5)

        self.assertEqual(
            compacted,
            [
                {
                    "path": "$.valid.path",
                    "message": "valid message",
                    "severity": "warning",
                }
            ],
        )

    def test_compact_validation_log_for_instruction_returns_non_dict_unchanged(self):
        validation_log = ["invalid-structure"]

        compact_log = _compact_validation_log_for_instruction(validation_log)

        self.assertIs(compact_log, validation_log)

    def test_extract_ocr_confidence_recurses_through_nested_wrappers(self):
        scenarios = (
            ({"ocr_metadata": {"confidence_score": 88.0}}, 88.0),
            ({"original_input_json": {"ocr_metadata": {"confidence_score": 77.0}}}, 77.0),
            ({"input_json": {"ocr_metadata": {"confidence_score": 66.0}}}, 66.0),
            ({"payload": {"ocr_metadata": {"confidence_score": 55.0}}}, 55.0),
            ({"not": "dict"}, None),
        )

        for payload, expected in scenarios:
            with self.subTest(payload=payload):
                self.assertEqual(_extract_ocr_confidence(payload), expected)

    def test_extract_ocr_confidence_ignores_non_numeric_direct_score_and_falls_back(self):
        payload = {
            "ocr_metadata": {"confidence_score": "high"},
            "input_json": {"ocr_metadata": {"confidence_score": 44.0}},
        }

        self.assertEqual(_extract_ocr_confidence(payload), 44.0)


class RefinementOrchestratorTest(SimpleTestCase):
    def _build_reasoning_service(self):
        return Mock()

    def test_orchestrator_stops_early_when_first_iteration_is_valid(self):
        generation_service = Mock()
        generation_service.generate.return_value = {
            "document_info": {"source_type": "Excel", "filename": "report.xlsx"},
            "summary": {"total_tables": 1},
            "content_data": [
                {
                    "table_name": "Sheet1",
                    "headers": ["item"],
                    "rows": [{"item": "Pen"}],
                }
            ],
        }
        reasoning_service = self._build_reasoning_service()
        reasoning_service.generate.return_value = {
            "final_answer": "valid",
            "reasoning_steps": ["validated"],
            "thinking_log": "iteration 1",
        }

        orchestrator = RefinementOrchestrator(
            generation_service=generation_service,
            reasoning_service=reasoning_service,
        )
        result = orchestrator.run(
            input_json={"filename": "report.xlsx"},
            custom_schema_id=None,
            include_reasoning=True,
            refinement_config=RefinementConfig(
                enabled=True,
                max_iterations=3,
                early_exit_on_valid=True,
            ),
        )

        self.assertEqual(result["refinement_meta"]["iterations_run"], 1)
        self.assertTrue(result["refinement_meta"]["early_exit_triggered"])
        self.assertEqual(result["refinement_meta"]["final_status"], "valid")
        self.assertEqual(generation_service.generate.call_count, 1)

    def test_orchestrator_runs_until_max_iterations_when_always_invalid(self):
        generation_service = Mock()
        generation_service.generate.side_effect = [
            {"status": "invalid-1"},
            {"status": "invalid-2"},
            {"status": "invalid-3"},
        ]

        orchestrator = RefinementOrchestrator(generation_service=generation_service)
        result = orchestrator.run(
            input_json={"filename": "report.xlsx"},
            custom_schema_id=None,
            include_reasoning=False,
            refinement_config=RefinementConfig(
                enabled=True,
                max_iterations=3,
                early_exit_on_valid=True,
            ),
        )

        self.assertEqual(result["refinement_meta"]["iterations_run"], 3)
        self.assertFalse(result["refinement_meta"]["early_exit_triggered"])
        self.assertEqual(result["refinement_meta"]["final_status"], "best_effort")
        self.assertEqual(generation_service.generate.call_count, 3)

    def test_orchestrator_selects_best_candidate_after_partial_improvement(self):
        generation_service = Mock()
        generation_service.generate.side_effect = [
            {"status": "invalid"},
            {
                "document_info": {"source_type": "Excel", "filename": "report.xlsx"},
                "summary": {"total_tables": 1},
                "content_data": [
                    {
                        "table_name": "Sheet1",
                        "headers": ["item"],
                        "rows": [{"item": "Pen"}],
                    }
                ],
            },
            {"status": "invalid-again"},
        ]

        orchestrator = RefinementOrchestrator(generation_service=generation_service)
        result = orchestrator.run(
            input_json={"filename": "report.xlsx"},
            custom_schema_id=None,
            include_reasoning=False,
            refinement_config=RefinementConfig(
                enabled=True,
                max_iterations=3,
                early_exit_on_valid=False,
            ),
        )

        self.assertEqual(result["refinement_meta"]["final_status"], "valid")
        self.assertEqual(result["validated_json"]["document_info"]["filename"], "report.xlsx")

    def test_orchestrator_calls_reasoning_service_once_for_best_candidate_when_enabled(self):
        generation_service = Mock()
        generation_service.generate.side_effect = [
            {"status": "invalid-1"},
            {"status": "invalid-2"},
            {"status": "invalid-3"},
        ]
        reasoning_service = self._build_reasoning_service()
        reasoning_service.generate.return_value = {
            "final_answer": "iterative",
            "reasoning_steps": ["step"],
            "thinking_log": "log",
        }

        orchestrator = RefinementOrchestrator(
            generation_service=generation_service,
            reasoning_service=reasoning_service,
        )
        orchestrator.run(
            input_json={"filename": "report.xlsx"},
            custom_schema_id=None,
            include_reasoning=True,
            refinement_config=RefinementConfig(
                enabled=True,
                max_iterations=3,
                early_exit_on_valid=False,
            ),
        )

        self.assertEqual(reasoning_service.generate.call_count, 1)

    @patch("llm.services.refinement_service.generate_conversion_reasoning_response")
    def test_orchestrator_continues_when_reasoning_generation_fails(
        self,
        mock_generate_reasoning,
    ):
        generation_service = Mock()
        generation_service.generate.side_effect = [
            {"status": "invalid-1"},
            {"status": "invalid-2"},
        ]
        mock_generate_reasoning.side_effect = RuntimeError("reasoning failed")

        orchestrator = RefinementOrchestrator(
            generation_service=generation_service,
            reasoning_service=self._build_reasoning_service(),
        )
        result = orchestrator.run(
            input_json={"filename": "report.xlsx"},
            custom_schema_id=None,
            include_reasoning=True,
            refinement_config=RefinementConfig(
                enabled=True,
                max_iterations=2,
                early_exit_on_valid=False,
            ),
        )

        self.assertEqual(result["refinement_meta"]["iterations_run"], 2)
        self.assertIsNone(result["reasoning"])

    @patch("llm.services.refinement_service.generate_conversion_reasoning_response")
    def test_orchestrator_returns_reasoning_for_best_candidate_when_last_iteration_is_worse(
        self,
        mock_generate_reasoning,
    ):
        generation_service = Mock()
        generation_service.generate.side_effect = [
            {"status": "invalid-1"},
            {
                "document_info": {"source_type": "Excel", "filename": "report.xlsx"},
                "summary": {"total_tables": 1},
                "content_data": [
                    {
                        "table_name": "Sheet1",
                        "headers": ["item"],
                        "rows": [{"item": "Pen"}],
                    }
                ],
            },
            {"status": "invalid-3"},
        ]
        mock_generate_reasoning.return_value = {
            "final_answer": "iter 2",
            "reasoning_steps": ["step-2"],
            "thinking_log": "log-2",
        }

        orchestrator = RefinementOrchestrator(
            generation_service=generation_service,
            reasoning_service=self._build_reasoning_service(),
        )
        result = orchestrator.run(
            input_json={"filename": "report.xlsx"},
            custom_schema_id=None,
            include_reasoning=True,
            refinement_config=RefinementConfig(
                enabled=True,
                max_iterations=3,
                early_exit_on_valid=False,
            ),
        )

        self.assertEqual(result["validated_json"]["document_info"]["filename"], "report.xlsx")
        self.assertEqual(result["reasoning"]["final_answer"], "iter 2")
        mock_generate_reasoning.assert_called_once()
        self.assertEqual(
            mock_generate_reasoning.call_args.kwargs["output_json"]["document_info"]["filename"],
            "report.xlsx",
        )

    def test_orchestrator_builds_refinement_instruction_from_previous_iteration(self):
        generation_service = Mock()
        generation_service.generate.side_effect = [
            {"status": "invalid-1"},
            {"status": "invalid-2"},
        ]

        orchestrator = RefinementOrchestrator(generation_service=generation_service)
        orchestrator.run(
            input_json={"filename": "report.xlsx", "headers": ["ID"]},
            custom_schema_id=None,
            include_reasoning=False,
            refinement_config=RefinementConfig(
                enabled=True,
                max_iterations=2,
                early_exit_on_valid=False,
            ),
        )

        self.assertEqual(generation_service.generate.call_count, 2)
        first_call_kwargs = generation_service.generate.call_args_list[0].kwargs
        second_call_kwargs = generation_service.generate.call_args_list[1].kwargs

        self.assertIsNone(first_call_kwargs["refinement_instruction"])
        self.assertIsInstance(second_call_kwargs["input_json"], dict)
        self.assertIn("previous_output_json", second_call_kwargs["input_json"])
        self.assertIsInstance(second_call_kwargs["refinement_instruction"], str)

    def test_orchestrator_passes_chat_context_to_all_iterations(self):
        generation_service = Mock()
        generation_service.generate.side_effect = [
            {"status": "invalid-1"},
            {"status": "invalid-2"},
        ]

        orchestrator = RefinementOrchestrator(generation_service=generation_service)
        orchestrator.run(
            input_json={"filename": "report.xlsx", "headers": ["ID"]},
            custom_schema_id=None,
            include_reasoning=False,
            refinement_config=RefinementConfig(
                enabled=True,
                max_iterations=2,
                early_exit_on_valid=False,
            ),
            chat_context="USER: Keep Indonesian headers",
        )

        first_call_kwargs = generation_service.generate.call_args_list[0].kwargs
        second_call_kwargs = generation_service.generate.call_args_list[1].kwargs
        self.assertEqual(first_call_kwargs["chat_context"], "USER: Keep Indonesian headers")
        self.assertEqual(second_call_kwargs["chat_context"], "USER: Keep Indonesian headers")

    # Positive
    def test_positive_valid_payload_has_valid_verdict_on_first_iteration(self):
        generation_service = Mock()
        generation_service.generate.return_value = {
            "document_info": {"source_type": "Excel", "filename": "ok.xlsx"},
            "summary": {"total_tables": 1},
            "content_data": [
                {
                    "table_name": "Sheet1",
                    "headers": ["item"],
                    "rows": [{"item": "Pen"}],
                }
            ],
        }
        orchestrator = RefinementOrchestrator(generation_service=generation_service)

        result = orchestrator.run(
            input_json={"filename": "ok.xlsx"},
            custom_schema_id=None,
            include_reasoning=False,
            refinement_config=RefinementConfig(
                enabled=True,
                max_iterations=3,
                early_exit_on_valid=True,
            ),
        )

        self.assertEqual(result["validation_log"]["verdict"], "valid")
        self.assertEqual(result["refinement_meta"]["iterations_run"], 1)

    # Negative
    def test_negative_invalid_payload_remains_best_effort_after_max_iterations(self):
        generation_service = Mock()
        generation_service.generate.side_effect = [
            {"document_info": {}},
            {"document_info": {}},
            {"document_info": {}},
        ]
        orchestrator = RefinementOrchestrator(generation_service=generation_service)

        result = orchestrator.run(
            input_json={"filename": "bad.xlsx"},
            custom_schema_id=None,
            include_reasoning=False,
            refinement_config=RefinementConfig(
                enabled=True,
                max_iterations=3,
                early_exit_on_valid=True,
            ),
        )

        self.assertEqual(result["refinement_meta"]["iterations_run"], 3)
        self.assertEqual(result["refinement_meta"]["final_status"], "best_effort")
        self.assertEqual(result["validation_log"]["verdict"], "invalid")

    def test_orchestrator_stops_early_on_plateau_without_valid_candidate(self):
        generation_service = Mock()
        generation_service.generate.side_effect = [
            {"status": "invalid-1"},
            {"status": "invalid-2"},
            {"status": "invalid-3"},
            {"status": "invalid-4"},
            {"status": "invalid-5"},
        ]
        orchestrator = RefinementOrchestrator(generation_service=generation_service)

        result = orchestrator.run(
            input_json={"filename": "bad.xlsx"},
            custom_schema_id=None,
            include_reasoning=False,
            refinement_config=RefinementConfig(
                enabled=True,
                max_iterations=5,
                early_exit_on_valid=False,
                early_exit_on_plateau=True,
                plateau_patience=2,
            ),
        )

        self.assertEqual(result["refinement_meta"]["iterations_run"], 3)
        self.assertTrue(result["refinement_meta"]["early_exit_triggered"])
        self.assertEqual(result["refinement_meta"]["final_status"], "best_effort")
        self.assertEqual(generation_service.generate.call_count, 3)

    def test_orchestrator_respects_plateau_disable_and_runs_full_iterations(self):
        generation_service = Mock()
        generation_service.generate.side_effect = [
            {"status": "invalid-1"},
            {"status": "invalid-2"},
            {"status": "invalid-3"},
            {"status": "invalid-4"},
            {"status": "invalid-5"},
        ]
        orchestrator = RefinementOrchestrator(generation_service=generation_service)

        result = orchestrator.run(
            input_json={"filename": "bad.xlsx"},
            custom_schema_id=None,
            include_reasoning=False,
            refinement_config=RefinementConfig(
                enabled=True,
                max_iterations=5,
                early_exit_on_valid=False,
                early_exit_on_plateau=False,
                plateau_patience=2,
            ),
        )

        self.assertEqual(result["refinement_meta"]["iterations_run"], 5)
        self.assertFalse(result["refinement_meta"]["early_exit_triggered"])
        self.assertEqual(generation_service.generate.call_count, 5)

    # Edge
    def test_edge_non_positive_max_iterations_is_normalized_to_single_iteration(self):
        generation_service = Mock()
        generation_service.generate.return_value = {
            "document_info": {"source_type": "Excel", "filename": "ok.xlsx"},
            "summary": {"total_tables": 1},
            "content_data": [
                {
                    "table_name": "Sheet1",
                    "headers": ["item"],
                    "rows": [{"item": "Pen"}],
                }
            ],
        }
        orchestrator = RefinementOrchestrator(generation_service=generation_service)

        result = orchestrator.run(
            input_json={"filename": "ok.xlsx"},
            custom_schema_id=None,
            include_reasoning=False,
            refinement_config=RefinementConfig(
                enabled=True,
                max_iterations=0,
                early_exit_on_valid=True,
            ),
        )

        self.assertEqual(result["refinement_meta"]["iterations_run"], 1)
        self.assertEqual(generation_service.generate.call_count, 1)
