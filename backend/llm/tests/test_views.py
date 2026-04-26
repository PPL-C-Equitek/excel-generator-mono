from types import SimpleNamespace

from django.test import SimpleTestCase, TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework.response import Response
from unittest.mock import patch
from uuid import uuid4

from artifact_history.models import ArtifactHistory
from authentication.models import User
from chat_sessions.models import ChatMessage, GeneratedOutput, Session
from llm.services.generation_service import CustomSchemaNotFoundError
from llm.services.openai_client import OpenAITextGenerationProvider
from llm.services.openai_client import (
    OpenAIConfigurationError,
    OpenAIServiceError,
    OpenAIUpstreamError,
)
from llm.views import (
    build_export_output_json,
    _extract_document_type,
    _sanitize_output_json,
    build_llm_generation_service,
    build_llm_reasoning_service,
    extract_original_name,
    get_authenticated_user_id,
)
from llm.serializers import MAX_MESSAGE_LENGTH

class LlmGenerateEndpointTest(SimpleTestCase):
    def test_build_llm_generation_service_returns_default_dependencies(self):
        service = build_llm_generation_service()

        self.assertEqual(service.__class__.__name__, "LlmGenerationService")
        self.assertEqual(service.json_generator.__class__.__name__, "JsonGenerationService")
        self.assertIsInstance(service.json_generator.text_provider, OpenAITextGenerationProvider)
        self.assertEqual(
            service.schema_prompt_source.__class__.__name__,
            "DjangoCustomSchemaPromptSource",
        )
        self.assertIsNone(service.schema_prompt_source.owner_id)

    def test_build_llm_generation_service_uses_authenticated_user_id_for_schema_source(self):
        owner_id = uuid4()

        service = build_llm_generation_service(
            SimpleNamespace(id=owner_id, is_authenticated=True)
        )

        self.assertEqual(service.schema_prompt_source.owner_id, owner_id)

    def test_get_authenticated_user_id_returns_none_for_anonymous_user(self):
        result = get_authenticated_user_id(SimpleNamespace(is_authenticated=False))

        self.assertIsNone(result)

    def test_extract_original_name_uses_input_document_info_filename(self):
        result = extract_original_name(
            {"document_info": {"filename": "input-doc.pdf"}},
            {"document_info": {"filename": "output-doc.pdf"}},
        )

        self.assertEqual(result, "input-doc.pdf")

    def test_extract_original_name_falls_back_to_output_document_info_filename(self):
        result = extract_original_name(
            {"document_info": {}},
            {"document_info": {"filename": "output-doc.pdf"}},
        )

        self.assertEqual(result, "output-doc.pdf")

    def test_extract_original_name_returns_generated_output_when_no_filename_available(self):
        result = extract_original_name(
            {"document_info": {}},
            {"document_info": {}},
        )

        self.assertEqual(result, "generated-output")

    def test_extract_original_name_returns_generated_output_when_input_and_output_are_not_objects(self):
        result = extract_original_name([], [])

        self.assertEqual(result, "generated-output")

    def test_extract_original_name_returns_generated_output_when_document_info_values_are_not_objects(self):
        result = extract_original_name(
            {"document_info": "not-an-object"},
            {"document_info": "not-an-object"},
        )

        self.assertEqual(result, "generated-output")

    def test_extract_document_type_returns_unknown_for_non_object_payload(self):
        result = _extract_document_type(["not-an-object"])

        self.assertEqual(result, "unknown")

    def test_extract_document_type_supports_file_type_and_format_keys(self):
        file_type_result = _extract_document_type({"file_type": " XLSX "})
        format_result = _extract_document_type({"format": " CSV "})

        self.assertEqual(file_type_result, "xlsx")
        self.assertEqual(format_result, "csv")

    def test_sanitize_output_json_removes_reasoning_meta_keys_from_object(self):
        sanitized = _sanitize_output_json(
            {
                "headers": ["A", "B"],
                "rows": [["1", "2"]],
                "final_answer": "should be removed",
                "reasoning_steps": ["should be removed"],
                "thinking_log": "should be removed",
            }
        )

        self.assertEqual(
            sanitized,
            {
                "headers": ["A", "B"],
                "rows": [["1", "2"]],
            },
        )

    def test_sanitize_output_json_keeps_non_object_payload_unchanged(self):
        payload = [{"row": 1}]
        sanitized = _sanitize_output_json(payload)

        self.assertEqual(sanitized, payload)

    def test_build_export_output_json_normalizes_headers_and_rows_payload(self):
        raw_output_json = {
            "headers": ["unit", "value"],
            "rows": [["ICU", 1000], ["ER", 1500]],
            "final_answer": "ignored for export payload",
        }
        input_json = {
            "filename": "hospital-report.xlsx",
            "document_info": {"source_type": "Excel"},
        }

        export_output_json = build_export_output_json(
            input_json=input_json,
            output_json=raw_output_json,
        )

        self.assertEqual(
            export_output_json,
            {
                "document_info": {
                    "source_type": "Excel",
                    "filename": "hospital-report.xlsx",
                },
                "summary": {
                    "total_tables": 1,
                    "total_rows": 2,
                    "total_columns": 2,
                },
                "content_data": [
                    {
                        "table_name": "Sheet1",
                        "headers": ["unit", "value"],
                        "rows": [
                            {"unit": "ICU", "value": 1000},
                            {"unit": "ER", "value": 1500},
                        ],
                    }
                ],
            },
        )

    def test_build_export_output_json_normalizes_sheet_like_mapping_payload(self):
        raw_output_json = {
            "Rawat Jalan": [
                {"unit": "Rawat Jalan", "value": 1000},
                {"unit": "Rawat Jalan", "value": 1200},
            ],
            "ICU": [
                {"unit": "ICU", "value": 3000},
            ],
        }
        input_json = {
            "document_info": {
                "filename": "finance.pdf",
                "source_type": "PDF",
            }
        }

        export_output_json = build_export_output_json(
            input_json=input_json,
            output_json=raw_output_json,
        )

        self.assertEqual(
            export_output_json["document_info"],
            {
                "source_type": "PDF",
                "filename": "finance.pdf",
            },
        )
        self.assertEqual(
            export_output_json["summary"],
            {
                "total_tables": 2,
                "total_rows": 3,
                "total_columns": 2,
            },
        )
        self.assertEqual(
            export_output_json["content_data"],
            [
                {
                    "table_name": "Rawat Jalan",
                    "headers": ["unit", "value"],
                    "rows": [
                        {"unit": "Rawat Jalan", "value": 1000},
                        {"unit": "Rawat Jalan", "value": 1200},
                    ],
                },
                {
                    "table_name": "ICU",
                    "headers": ["unit", "value"],
                    "rows": [
                        {"unit": "ICU", "value": 3000},
                    ],
                },
            ],
        )

    def test_build_export_output_json_infers_pdf_source_type_from_filename(self):
        export_output_json = build_export_output_json(
            input_json={"document_info": {"filename": "invoice.pdf"}},
            output_json={"headers": ["unit"], "rows": [["ICU"]]},
        )

        self.assertEqual(
            export_output_json["document_info"],
            {
                "source_type": "PDF",
                "filename": "invoice.pdf",
            },
        )

    def test_build_export_output_json_falls_back_to_excel_when_source_type_is_unrecognized(self):
        export_output_json = build_export_output_json(
            input_json={
                "document_info": {
                    "filename": "invoice.docx",
                    "source_type": "word",
                }
            },
            output_json={"headers": ["unit"], "rows": [["ICU"]]},
        )

        self.assertEqual(
            export_output_json["document_info"],
            {
                "source_type": "Excel",
                "filename": "invoice.docx",
            },
        )

    def test_build_export_output_json_normalizes_duplicate_blank_headers_and_mixed_rows(self):
        export_output_json = build_export_output_json(
            input_json={"document_info": {"source_type": "xlsx"}},
            output_json={
                "headers": [" Unit ", "", "unit"],
                "rows": [
                    ["ICU", 10, 20],
                    {"Unit": "ER", "column_2": 30, "unit_2": 40},
                    "fallback",
                ],
            },
        )

        self.assertEqual(
            export_output_json["content_data"],
            [
                {
                    "table_name": "Sheet1",
                    "headers": ["Unit", "column_2", "unit_2"],
                    "rows": [
                        {"Unit": "ICU", "column_2": 10, "unit_2": 20},
                        {"Unit": "ER", "column_2": 30, "unit_2": 40},
                        {"Unit": "fallback", "column_2": None, "unit_2": None},
                    ],
                }
            ],
        )

    def test_build_export_output_json_uses_sheet_fallback_name_for_blank_sheet_key(self):
        export_output_json = build_export_output_json(
            input_json={"filename": "summary.xlsx"},
            output_json={
                "   ": [1, 2],
                "Named": [{"value": 3, "other": "ok"}],
            },
        )

        self.assertEqual(
            export_output_json["content_data"],
            [
                {
                    "table_name": "Sheet1",
                    "headers": ["value"],
                    "rows": [{"value": 1}, {"value": 2}],
                },
                {
                    "table_name": "Named",
                    "headers": ["value", "other"],
                    "rows": [{"value": 3, "other": "ok"}],
                },
            ],
        )

    def test_build_export_output_json_wraps_scalar_payload_in_default_value_table(self):
        export_output_json = build_export_output_json(
            input_json={"filename": "summary.xlsx"},
            output_json=123,
        )

        self.assertEqual(
            export_output_json["content_data"],
            [
                {
                    "table_name": "Sheet1",
                    "headers": ["value"],
                    "rows": [{"value": 123}],
                }
            ],
        )
        self.assertEqual(
            export_output_json["summary"],
            {"total_tables": 1, "total_rows": 1, "total_columns": 1},
        )

    def test_build_export_output_json_uses_default_value_header_for_empty_headers(self):
        export_output_json = build_export_output_json(
            input_json={"filename": "summary.xlsx"},
            output_json={
                "headers": [],
                "rows": [[{"bad"}]],
            },
        )

        self.assertEqual(
            export_output_json["content_data"],
            [
                {
                    "table_name": "Sheet1",
                    "headers": ["value"],
                    "rows": [{"value": "[Unserializable Value]"}],
                }
            ],
        )

    def test_build_export_output_json_infers_headers_from_list_of_lists_payload(self):
        export_output_json = build_export_output_json(
            input_json={"filename": "summary.xlsx"},
            output_json=[["ICU", 10], ["ER", 20]],
        )

        self.assertEqual(
            export_output_json["content_data"],
            [
                {
                    "table_name": "Sheet1",
                    "headers": ["column_1", "column_2"],
                    "rows": [
                        {"column_1": "ICU", "column_2": 10},
                        {"column_1": "ER", "column_2": 20},
                    ],
                }
            ],
        )

    @patch("llm.views.build_llm_generation_service")
    def test_llm_generate_returns_200(self, mock_build_service):
        mock_service = mock_build_service.return_value
        mock_service.generate.return_value = {"status": "ok"}
        client = APIClient()

        payload = {"input_json": {"sheet": "Sheet1"}}
        response = client.post("/llm/generate/", payload, format="json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["output_json"], {"status": "ok"})
        self.assertIsNone(response.data["output_id"])
        self.assertEqual(mock_build_service.call_count, 1)
        self.assertFalse(mock_build_service.call_args[0][0].is_authenticated)
        mock_service.generate.assert_called_once_with(
            input_json={"sheet": "Sheet1"},
            custom_schema_id=None,
        )

    @patch("llm.views.build_llm_reasoning_service")
    @patch("llm.views.build_llm_generation_service")
    def test_llm_generate_calls_reasoning_by_default(
        self,
        mock_build_generation_service,
        mock_build_reasoning_service,
    ):
        mock_generation_service = mock_build_generation_service.return_value
        mock_generation_service.generate.return_value = {"status": "ok"}
        mock_reasoning_service = mock_build_reasoning_service.return_value
        mock_reasoning_service.generate.return_value = {
            "final_answer": "Conversion looks consistent.",
            "reasoning_steps": ["Mapped source fields to normalized headers."],
            "thinking_log": "Checked mapping, ambiguity, and output consistency.",
        }
        client = APIClient()

        response = client.post(
            "/llm/generate/",
            {"input_json": {"sheet": "Sheet1"}},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["output_json"], {"status": "ok"})
        self.assertEqual(response.data["reasoning"]["final_answer"], "Conversion looks consistent.")
        mock_reasoning_service.generate.assert_called_once()

    @patch("llm.views.build_llm_generation_service")
    def test_llm_generate_strips_reasoning_keys_from_output_json(self, mock_build_service):
        mock_service = mock_build_service.return_value
        mock_service.generate.return_value = {
            "headers": ["A", "B"],
            "rows": [["1", "2"]],
            "final_answer": "remove me",
            "reasoning_steps": ["remove me"],
            "thinking_log": "remove me",
        }
        client = APIClient()

        response = client.post(
            "/llm/generate/",
            {"input_json": {"sheet": "Sheet1"}, "include_reasoning": False},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["output_json"],
            {
                "headers": ["A", "B"],
                "rows": [["1", "2"]],
            },
        )

    @patch("llm.views.build_llm_reasoning_service")
    @patch("llm.views.build_llm_generation_service")
    def test_llm_generate_skips_reasoning_when_include_reasoning_false(
        self,
        mock_build_generation_service,
        mock_build_reasoning_service,
    ):
        mock_generation_service = mock_build_generation_service.return_value
        mock_generation_service.generate.return_value = {"status": "ok"}
        client = APIClient()

        response = client.post(
            "/llm/generate/",
            {
                "input_json": {"sheet": "Sheet1"},
                "include_reasoning": False,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["output_json"], {"status": "ok"})
        self.assertIsNone(response.data["reasoning"])
        mock_build_reasoning_service.assert_not_called()

    @patch("llm.views.logger")
    @patch("llm.views.generate_conversion_reasoning_response")
    @patch("llm.views.build_llm_reasoning_service")
    @patch("llm.views.build_llm_generation_service")
    def test_llm_generate_sets_reasoning_none_when_unexpected_auto_reasoning_error_occurs(
        self,
        mock_build_generation_service,
        mock_build_reasoning_service,
        mock_generate_conversion_reasoning,
        mock_logger,
    ):
        mock_generation_service = mock_build_generation_service.return_value
        mock_generation_service.generate.return_value = {"status": "ok"}
        mock_generate_conversion_reasoning.side_effect = RuntimeError("unexpected")
        client = APIClient()

        response = client.post(
            "/llm/generate/",
            {"input_json": {"sheet": "Sheet1"}},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["output_json"], {"status": "ok"})
        self.assertIsNone(response.data["reasoning"])
        mock_build_reasoning_service.assert_called_once()
        mock_generate_conversion_reasoning.assert_called_once()
        mock_logger.exception.assert_called_once_with(
            "Unexpected error while generating automatic reasoning."
        )

    @patch("llm.views.logger")
    @patch("llm.views.generate_conversion_reasoning_response")
    @patch("llm.views.build_llm_reasoning_service")
    @patch("llm.views.build_llm_generation_service")
    def test_llm_generate_sets_reasoning_none_when_expected_auto_reasoning_error_occurs(
        self,
        mock_build_generation_service,
        mock_build_reasoning_service,
        mock_generate_conversion_reasoning,
        mock_logger,
    ):
        mock_generation_service = mock_build_generation_service.return_value
        mock_generation_service.generate.return_value = {"status": "ok"}
        mock_generate_conversion_reasoning.side_effect = OpenAIServiceError(
            "invalid reasoning payload"
        )
        client = APIClient()

        response = client.post(
            "/llm/generate/",
            {"input_json": {"sheet": "Sheet1"}},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["output_json"], {"status": "ok"})
        self.assertIsNone(response.data["reasoning"])
        mock_build_reasoning_service.assert_called_once()
        mock_generate_conversion_reasoning.assert_called_once()
        mock_logger.exception.assert_called_once_with(
            "Automatic reasoning failed while handling llm_generate request."
        )

    @patch("llm.views.build_llm_generation_service")
    def test_llm_generate_passes_selected_schema_id_to_generation_service(
        self, mock_build_service
    ):
        mock_service = mock_build_service.return_value
        mock_service.generate.return_value = {"status": "ok"}
        client = APIClient()
        schema_id = uuid4()

        response = client.post(
            "/llm/generate/",
            {"input_json": {"sheet": "Sheet1"}, "custom_schema_id": str(schema_id)},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(mock_build_service.call_count, 1)
        self.assertFalse(mock_build_service.call_args[0][0].is_authenticated)
        mock_service.generate.assert_called_once_with(
            input_json={"sheet": "Sheet1"},
            custom_schema_id=schema_id,
        )

    @patch("llm.views.build_llm_generation_service")
    def test_llm_generate_returns_404_when_selected_schema_missing(
        self, mock_build_service
    ):
        client = APIClient()
        schema_id = uuid4()
        mock_service = mock_build_service.return_value
        mock_service.generate.side_effect = CustomSchemaNotFoundError(
            "Custom schema not found."
        )

        response = client.post(
            "/llm/generate/",
            {"input_json": {"sheet": "Sheet1"}, "custom_schema_id": str(schema_id)},
            format="json",
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data["detail"], "Custom schema not found.")
        self.assertEqual(mock_build_service.call_count, 1)
        self.assertFalse(mock_build_service.call_args[0][0].is_authenticated)
        mock_service.generate.assert_called_once_with(
            input_json={"sheet": "Sheet1"},
            custom_schema_id=schema_id,
        )

    def test_llm_generate_rejects_missing_input_json(self):
        client = APIClient()
        response = client.post("/llm/generate/", {}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["detail"], "Invalid request payload.")
        self.assertIn("errors", response.data)

    def test_llm_generate_rejects_non_object_or_array_input_json(self):
        client = APIClient()
        response = client.post("/llm/generate/", {"input_json": "not-json-object"}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["detail"], "Invalid request payload.")
        self.assertIn("errors", response.data)

    def test_llm_generate_rejects_invalid_custom_schema_id(self):
        client = APIClient()
        response = client.post(
            "/llm/generate/",
            {"input_json": {"sheet": "Sheet1"}, "custom_schema_id": "not-a-uuid"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["detail"], "Invalid request payload.")
        self.assertIn("errors", response.data)

    def test_llm_generate_rejects_client_model_field(self):
        client = APIClient()
        response = client.post(
            "/llm/generate/",
            {"input_json": {"ok": True}, "model": "gpt-4.1-mini"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["detail"], "Invalid request payload.")
        self.assertIn("errors", response.data)

    @patch("llm.views.build_llm_generation_service")
    def test_llm_generate_returns_503_for_service_error(self, mock_build_service):
        mock_service = mock_build_service.return_value
        mock_service.generate.side_effect = OpenAIConfigurationError(
            "OPENAI_API_KEY is not configured."
        )
        client = APIClient()

        response = client.post("/llm/generate/", {"input_json": {"hello": "world"}}, format="json")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data["detail"], "Service unavailable. Please try again later.")

    @patch("llm.views.build_llm_generation_service")
    def test_llm_generate_returns_502_for_invalid_json_response(self, mock_build_service):
        mock_service = mock_build_service.return_value
        mock_service.generate.side_effect = OpenAIServiceError(
            "OpenAI response is not valid JSON."
        )
        client = APIClient()

        response = client.post("/llm/generate/", {"input_json": {"hello": "world"}}, format="json")

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.data["detail"], "Failed to generate response from LLM provider.")

    @patch("llm.views.logger")
    @patch("llm.views.build_llm_generation_service")
    def test_llm_generate_returns_502_for_upstream_auth_error(self, mock_build_service, mock_logger):
        mock_service = mock_build_service.return_value
        mock_service.generate.side_effect = OpenAIUpstreamError(
            "LLM authentication failed.",
            status_code=502,
        )
        client = APIClient()

        response = client.post("/llm/generate/", {"input_json": {"hello": "world"}}, format="json")

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.data["detail"], "Failed to generate response from LLM provider.")
        mock_logger.exception.assert_called_once_with("Upstream LLM provider error while handling llm_generate request.")

    @patch("llm.views.logger")
    @patch("llm.views.build_llm_generation_service")
    def test_llm_generate_returns_429_for_upstream_rate_limit(self, mock_build_service, mock_logger):
        mock_service = mock_build_service.return_value
        mock_service.generate.side_effect = OpenAIUpstreamError(
            "LLM rate limit exceeded.",
            status_code=429,
        )
        client = APIClient()

        response = client.post("/llm/generate/", {"input_json": {"hello": "world"}}, format="json")

        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.data["detail"], "Failed to generate response from LLM provider.")
        mock_logger.exception.assert_called_once_with("Upstream LLM provider error while handling llm_generate request.")

    @patch("llm.views.logger")
    @patch("llm.views.build_llm_generation_service")
    def test_llm_generate_returns_504_for_upstream_timeout(self, mock_build_service, mock_logger):
        mock_service = mock_build_service.return_value
        mock_service.generate.side_effect = OpenAIUpstreamError(
            "LLM request timed out.",
            status_code=504,
        )
        client = APIClient()

        response = client.post("/llm/generate/", {"input_json": {"hello": "world"}}, format="json")

        self.assertEqual(response.status_code, 504)
        self.assertEqual(response.data["detail"], "Failed to generate response from LLM provider.")
        mock_logger.exception.assert_called_once_with("Upstream LLM provider error while handling llm_generate request.")

    @patch("llm.views.logger")
    @patch("llm.views.build_llm_generation_service")
    def test_llm_generate_logs_upstream_error_without_exposing_exception(self, mock_build_service, mock_logger):
        mock_service = mock_build_service.return_value
        mock_service.generate.side_effect = OpenAIUpstreamError(
            "raw upstream details",
            status_code=502,
        )
        client = APIClient()

        response = client.post("/llm/generate/", {"input_json": {"hello": "world"}}, format="json")

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.data["detail"], "Failed to generate response from LLM provider.")
        self.assertNotIn("raw upstream details", response.data["detail"])
        mock_logger.exception.assert_called_once_with(
            "Upstream LLM provider error while handling llm_generate request."
        )

    @patch("llm.views.logger")
    @patch("llm.views.build_llm_generation_service")
    def test_llm_generate_returns_500_for_unexpected_error(self, mock_build_service, mock_logger):
        mock_service = mock_build_service.return_value
        mock_service.generate.side_effect = RuntimeError("upstream error")
        client = APIClient()

        response = client.post("/llm/generate/", {"input_json": {"hello": "world"}}, format="json")

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.data["detail"], "Internal server error.")
        mock_logger.exception.assert_called_once()

    @patch("llm.views.build_llm_reasoning_service")
    @patch("llm.views.LlmGenerateResponseSerializer")
    @patch("llm.views.build_llm_generation_service")
    def test_llm_generate_returns_502_when_response_serializer_invalid(
        self,
        mock_build_service,
        mock_response_serializer_class,
        mock_build_reasoning_service,
    ):
        mock_service = mock_build_service.return_value
        mock_service.generate.return_value = {"status": "ok"}
        mock_reasoning_service = mock_build_reasoning_service.return_value
        mock_reasoning_service.generate.return_value = {
            "final_answer": "Answer",
            "reasoning_steps": ["Step one"],
            "thinking_log": "Summary",
        }
        mock_response_serializer = mock_response_serializer_class.return_value
        mock_response_serializer.is_valid.return_value = False
        client = APIClient()

        response = client.post("/llm/generate/", {"input_json": {"hello": "world"}}, format="json")

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.data["detail"], "Failed to generate response from LLM provider.")
        mock_response_serializer_class.assert_called_once_with(
            data={
                "output_json": {"status": "ok"},
                "session_id": None,
                "output_id": None,
                "reasoning": {
                    "final_answer": "Answer",
                    "reasoning_steps": ["Step one"],
                    "thinking_log": "Summary",
                },
            }
        )

    @patch("llm.views.logger")
    @patch("llm.views.build_llm_generation_service")
    def test_llm_generate_returns_400_for_value_error(self, mock_build_service, mock_logger):
        mock_service = mock_build_service.return_value
        mock_service.generate.side_effect = ValueError(
            "input_json must be an object or array."
        )
        client = APIClient()

        response = client.post("/llm/generate/", {"input_json": {"hello": "world"}}, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["detail"], "Invalid request payload.")
        self.assertEqual(response.data["errors"]["input_json"], ["Invalid input_json payload."])
        mock_logger.exception.assert_called_once_with("Invalid input_json payload.")

    def test_llm_generate_rejects_non_json_content_type(self):
        client = APIClient()
        response = client.post("/llm/generate/", data="plain text", content_type="text/plain")
        self.assertEqual(response.status_code, 415)
        self.assertEqual(response.data["detail"], "Content-Type must be application/json.")

    def test_llm_generate_rejects_get(self):
        client = APIClient()
        response = client.get("/llm/generate/")
        self.assertEqual(response.status_code, 405)

    # @patch("llm.views.generate_json")
    # def test_llm_generate_rate_limited_5_per_minute(self, mock_generate_json):
    #     mock_generate_json.return_value = {"status": "ok"}
    #     client = APIClient()
    #     payload = {"input_json": {"hello": "world"}}

    #     for _ in range(5):
    #         response = client.post("/llm/generate/", payload, format="json", REMOTE_ADDR="127.0.0.99")
    #         self.assertEqual(response.status_code, 200)

    #     blocked = client.post("/llm/generate/", payload, format="json", REMOTE_ADDR="127.0.0.99")
    #     self.assertEqual(blocked.status_code, 429)
    #     self.assertIn("detail", blocked.data)
    #     self.assertEqual(blocked["X-RateLimit-Limit"], "5")


class LlmReasoningEndpointTest(SimpleTestCase):
    # Positive
    def test_build_llm_reasoning_service_returns_default_dependencies(self):
        service = build_llm_reasoning_service()

        self.assertEqual(service.__class__.__name__, "LlmReasoningService")
        self.assertIsInstance(service.text_provider, OpenAITextGenerationProvider)

    # Positive
    @patch("llm.views.build_llm_reasoning_service")
    def test_llm_reasoning_returns_200_for_authenticated_user(self, mock_build_service):
        mock_service = mock_build_service.return_value
        mock_service.generate.return_value = {
            "final_answer": "Total payment is Rp1.250.000.",
            "reasoning_steps": [
                "Identify the total amount.",
                "Confirm it is the final payable total.",
            ],
            "thinking_log": "The invoice total was identified and summarized.",
        }
        client = APIClient()
        client.force_authenticate(user=SimpleNamespace(is_authenticated=True, id="user-1"))

        response = client.post(
            "/llm/reasoning/",
            {"prompt": "Summarize this invoice"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["final_answer"], "Total payment is Rp1.250.000.")
        self.assertEqual(
            response.data["reasoning_steps"],
            [
                "Identify the total amount.",
                "Confirm it is the final payable total.",
            ],
        )
        self.assertEqual(
            response.data["thinking_log"],
            "The invoice total was identified and summarized.",
        )
        mock_service.generate.assert_called_once_with(prompt="Summarize this invoice")

    # Negative
    @patch("llm.views.build_llm_reasoning_service")
    def test_llm_reasoning_requires_authentication(self, mock_build_service):
        client = APIClient()

        response = client.post(
            "/llm/reasoning/",
            {"prompt": "Summarize this invoice"},
            format="json",
        )

        self.assertEqual(response.status_code, 401)
        mock_build_service.assert_not_called()

    # Negative
    @patch("llm.views.build_llm_reasoning_service")
    def test_llm_reasoning_rejects_invalid_token(self, mock_build_service):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer invalid.token")

        response = client.post(
            "/llm/reasoning/",
            {"prompt": "Summarize this invoice"},
            format="json",
        )

        self.assertEqual(response.status_code, 401)
        mock_build_service.assert_not_called()

    # Edge
    @patch("llm.views.build_llm_reasoning_service")
    def test_llm_reasoning_rejects_blank_prompt_without_calling_service(
        self, mock_build_service
    ):
        client = APIClient()
        client.force_authenticate(user=SimpleNamespace(is_authenticated=True, id="user-1"))

        response = client.post(
            "/llm/reasoning/",
            {"prompt": "   "},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["detail"], "Invalid request payload.")
        self.assertIn("errors", response.data)
        mock_build_service.assert_not_called()

    # Negative
    @patch("llm.views.LlmReasoningResponseSerializer")
    @patch("llm.views.build_llm_reasoning_service")
    def test_llm_reasoning_returns_502_when_response_serializer_invalid(
        self, mock_build_service, mock_response_serializer_class
    ):
        mock_service = mock_build_service.return_value
        mock_service.generate.return_value = {
            "final_answer": "Answer",
            "reasoning_steps": ["Step one"],
            "thinking_log": "Summary",
        }
        mock_response_serializer = mock_response_serializer_class.return_value
        mock_response_serializer.is_valid.return_value = False
        client = APIClient()
        client.force_authenticate(user=SimpleNamespace(is_authenticated=True, id="user-1"))

        response = client.post(
            "/llm/reasoning/",
            {"prompt": "Summarize this invoice"},
            format="json",
        )

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.data["detail"], "Failed to generate response from LLM provider.")

    # Negative
    @patch("llm.views.logger")
    @patch("llm.views.build_llm_reasoning_service")
    def test_llm_reasoning_returns_400_for_value_error(self, mock_build_service, mock_logger):
        mock_service = mock_build_service.return_value
        mock_service.generate.side_effect = ValueError("prompt must be a non-empty string.")
        client = APIClient()
        client.force_authenticate(user=SimpleNamespace(is_authenticated=True, id="user-1"))

        response = client.post(
            "/llm/reasoning/",
            {"prompt": "Summarize this invoice"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["detail"], "Invalid request payload.")
        self.assertEqual(response.data["errors"]["prompt"], ["Invalid prompt payload."])
        mock_logger.exception.assert_called_once_with("Invalid prompt payload.")

    # Negative
    @patch("llm.views.build_llm_reasoning_service")
    def test_llm_reasoning_returns_503_for_configuration_error(self, mock_build_service):
        mock_service = mock_build_service.return_value
        mock_service.generate.side_effect = OpenAIConfigurationError("OPENAI_API_KEY is not configured.")
        client = APIClient()
        client.force_authenticate(user=SimpleNamespace(is_authenticated=True, id="user-1"))

        response = client.post(
            "/llm/reasoning/",
            {"prompt": "Summarize this invoice"},
            format="json",
        )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data["detail"], "Service unavailable. Please try again later.")

    # Negative
    @patch("llm.views.build_llm_reasoning_service")
    def test_llm_reasoning_returns_502_for_provider_failure(self, mock_build_service):
        mock_service = mock_build_service.return_value
        mock_service.generate.side_effect = OpenAIServiceError("invalid response")
        client = APIClient()
        client.force_authenticate(user=SimpleNamespace(is_authenticated=True, id="user-1"))

        response = client.post(
            "/llm/reasoning/",
            {"prompt": "Summarize this invoice"},
            format="json",
        )

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.data["detail"], "Failed to generate response from LLM provider.")

    # Negative
    @patch("llm.views.logger")
    @patch("llm.views.build_llm_reasoning_service")
    def test_llm_reasoning_returns_upstream_status_code(self, mock_build_service, mock_logger):
        mock_service = mock_build_service.return_value
        mock_service.generate.side_effect = OpenAIUpstreamError(
            "LLM rate limit exceeded.",
            status_code=429,
        )
        client = APIClient()
        client.force_authenticate(user=SimpleNamespace(is_authenticated=True, id="user-1"))

        response = client.post(
            "/llm/reasoning/",
            {"prompt": "Summarize this invoice"},
            format="json",
        )

        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.data["detail"], "Failed to generate response from LLM provider.")
        mock_logger.exception.assert_called_once_with(
            "Upstream LLM provider error while handling llm_reasoning request."
        )

    # Edge
    @patch("llm.views.logger")
    @patch("llm.views.build_llm_reasoning_service")
    def test_llm_reasoning_returns_500_for_unexpected_error(self, mock_build_service, mock_logger):
        mock_service = mock_build_service.return_value
        mock_service.generate.side_effect = RuntimeError("unexpected")
        client = APIClient()
        client.force_authenticate(user=SimpleNamespace(is_authenticated=True, id="user-1"))

        response = client.post(
            "/llm/reasoning/",
            {"prompt": "Summarize this invoice"},
            format="json",
        )

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.data["detail"], "Internal server error.")
        mock_logger.exception.assert_called_once_with(
            "Unexpected error while handling llm_reasoning request."
        )

    # Negative
    def test_llm_reasoning_rejects_non_json_content_type(self):
        client = APIClient()
        client.force_authenticate(user=SimpleNamespace(is_authenticated=True, id="user-1"))

        response = client.post(
            "/llm/reasoning/",
            data="plain text",
            content_type="text/plain",
        )

        self.assertEqual(response.status_code, 415)
        self.assertEqual(response.data["detail"], "Content-Type must be application/json.")


class LlmGenerateSessionIntegrationTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="session-generate@example.com",
            name="Session Generate User",
            password="secret",
            status="verified",
        )
        self.output_json = {
            "document_info": {"filename": "invoice.pdf"},
            "summary": {"table_count": 1},
            "content_data": [{"table_name": "Sheet1", "headers": ["A"], "rows": [["1"]]}],
        }

    @patch("llm.views.build_llm_generation_service")
    def test_llm_generate_creates_session_and_generated_output_for_authenticated_user(
        self, mock_build_service
    ):
        mock_service = mock_build_service.return_value
        raw_output_json = {
            "headers": ["unit", "value"],
            "rows": [["ICU", 1000]],
            "final_answer": "Raw output for FE",
        }
        mock_service.generate.return_value = raw_output_json
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/llm/generate/",
            {
                "input_json": {
                    "filename": "invoice.pdf",
                    "extracted": "raw upload text",
                }
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("session_id", response.data)
        self.assertIn("output_id", response.data)
        self.assertEqual(Session.objects.count(), 1)
        session = Session.objects.get(owner=self.user)
        self.assertEqual(str(session.id), response.data["session_id"])
        self.assertEqual(GeneratedOutput.objects.count(), 1)
        generated_output = GeneratedOutput.objects.get(session=session)
        self.assertEqual(str(generated_output.id), response.data["output_id"])
        self.assertEqual(
            generated_output.output_json,
            {
                "headers": ["unit", "value"],
                "rows": [["ICU", 1000]],
            },
        )
        self.assertIsInstance(generated_output.thinking_log, str)
        self.assertEqual(
            generated_output.export_output_json,
            {
                "document_info": {
                    "source_type": "PDF",
                    "filename": "invoice.pdf",
                },
                "summary": {
                    "total_tables": 1,
                    "total_rows": 1,
                    "total_columns": 2,
                },
                "content_data": [
                    {
                        "table_name": "Sheet1",
                        "headers": ["unit", "value"],
                        "rows": [{"unit": "ICU", "value": 1000}],
                    }
                ],
            },
        )
        self.assertEqual(ArtifactHistory.objects.count(), 1)

    @patch("llm.views._generate_optional_reasoning")
    @patch("llm.views.build_llm_generation_service")
    def test_llm_generate_persists_thinking_log_from_reasoning_response(
        self,
        mock_build_service,
        mock_generate_reasoning,
    ):
        mock_service = mock_build_service.return_value
        mock_service.generate.return_value = {
            "headers": ["unit", "value"],
            "rows": [["ICU", 1000]],
        }
        mock_generate_reasoning.return_value = {
            "final_answer": "Done.",
            "reasoning_steps": ["Mapped rows."],
            "thinking_log": "Normalized columns and preserved totals.",
        }
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/llm/generate/",
            {
                "input_json": {
                    "filename": "invoice.pdf",
                    "extracted": "raw upload text",
                }
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        generated_output = GeneratedOutput.objects.get()
        self.assertEqual(
            generated_output.thinking_log,
            "Normalized columns and preserved totals.",
        )

    @patch("llm.views._generate_optional_reasoning")
    @patch("llm.views.build_llm_generation_service")
    def test_llm_generate_defaults_thinking_log_to_empty_when_reasoning_missing(
        self,
        mock_build_service,
        mock_generate_reasoning,
    ):
        mock_service = mock_build_service.return_value
        mock_service.generate.return_value = {
            "headers": ["unit", "value"],
            "rows": [["ICU", 1000]],
        }
        mock_generate_reasoning.return_value = None
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/llm/generate/",
            {
                "input_json": {
                    "filename": "invoice.pdf",
                    "extracted": "raw upload text",
                }
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        generated_output = GeneratedOutput.objects.get()
        self.assertEqual(generated_output.thinking_log, "")

    @patch("llm.views._build_generate_success_response")
    @patch("llm.views._generate_optional_reasoning")
    @patch("llm.views.build_llm_generation_service")
    def test_llm_generate_defaults_thinking_log_to_empty_when_reasoning_log_is_not_string(
        self,
        mock_build_service,
        mock_generate_reasoning,
        mock_build_success_response,
    ):
        mock_service = mock_build_service.return_value
        mock_service.generate.return_value = {
            "headers": ["unit", "value"],
            "rows": [["ICU", 1000]],
        }
        mock_generate_reasoning.return_value = {
            "final_answer": "Done.",
            "thinking_log": ["not", "a", "string"],
        }
        mock_build_success_response.return_value = Response({"status": "ok"})
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/llm/generate/",
            {
                "input_json": {
                    "filename": "invoice.pdf",
                    "extracted": "raw upload text",
                }
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        generated_output = GeneratedOutput.objects.get()
        self.assertEqual(generated_output.thinking_log, "")

    @patch("llm.views.build_llm_generation_service")
    def test_llm_generate_does_not_create_session_or_generated_output_when_generation_fails(
        self, mock_build_service
    ):
        mock_service = mock_build_service.return_value
        mock_service.generate.side_effect = RuntimeError("upstream error")
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/llm/generate/",
            {"input_json": {"filename": "invoice.pdf", "extracted": "raw upload text"}},
            format="json",
        )

        self.assertEqual(response.status_code, 500)
        self.assertFalse(Session.objects.exists())
        self.assertFalse(GeneratedOutput.objects.exists())
        self.assertFalse(ArtifactHistory.objects.exists())

    @patch("llm.views.build_llm_generation_service")
    def test_llm_generate_persists_sanitized_output_json_without_reasoning_keys(
        self,
        mock_build_service,
    ):
        mock_service = mock_build_service.return_value
        mock_service.generate.return_value = {
            "document_info": {"filename": "invoice.pdf"},
            "headers": ["A", "B"],
            "rows": [["1", "2"]],
            "final_answer": "remove me",
            "reasoning_steps": ["remove me"],
            "thinking_log": "remove me",
        }
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/llm/generate/",
            {
                "input_json": {
                    "filename": "invoice.pdf",
                    "extracted": "raw upload text",
                },
                "include_reasoning": False,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(ArtifactHistory.objects.count(), 1)
        history = ArtifactHistory.objects.get()
        self.assertNotIn("final_answer", history.output_json)
        self.assertNotIn("reasoning_steps", history.output_json)
        self.assertNotIn("thinking_log", history.output_json)
        self.assertEqual(
            history.output_json,
            {
                "document_info": {"filename": "invoice.pdf"},
                "headers": ["A", "B"],
                "rows": [["1", "2"]],
            },
        )

    @patch("llm.views.build_llm_generation_service")
    def test_llm_generate_reuses_existing_owned_session_when_session_id_is_provided(
        self, mock_build_service
    ):
        mock_service = mock_build_service.return_value
        raw_output_json = {
            "headers": ["unit", "value"],
            "rows": [["ICU", 1000]],
            "reasoning_steps": ["remove me from persisted raw payload"],
        }
        mock_service.generate.return_value = raw_output_json
        session = Session.objects.create(owner=self.user, title="Existing Session")
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/llm/generate/",
            {
                "input_json": {"filename": "invoice.pdf", "extracted": "raw upload text"},
                "session_id": str(session.id),
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["session_id"], str(session.id))
        self.assertEqual(Session.objects.count(), 1)
        self.assertEqual(GeneratedOutput.objects.count(), 1)
        generated_output = GeneratedOutput.objects.get()
        self.assertEqual(generated_output.session, session)
        self.assertEqual(response.data["output_id"], str(generated_output.id))
        self.assertEqual(
            generated_output.output_json,
            {
                "headers": ["unit", "value"],
                "rows": [["ICU", 1000]],
            },
        )
        self.assertEqual(
            generated_output.export_output_json["content_data"][0]["rows"],
            [{"unit": "ICU", "value": 1000}],
        )
        self.assertTrue(ArtifactHistory.objects.exists())

    @patch("llm.views.build_llm_generation_service")
    def test_llm_generate_updates_session_last_output_at(self, mock_build_service):
        mock_service = mock_build_service.return_value
        mock_service.generate.return_value = self.output_json
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/llm/generate/",
            {"input_json": {"filename": "invoice.pdf", "extracted": "raw upload text"}},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        session = Session.objects.get(owner=self.user)
        self.assertIsNotNone(session.last_output_at)

    @patch("llm.views.build_llm_generation_service")
    def test_llm_generate_creates_multiple_outputs_for_same_session(self, mock_build_service):
        mock_service = mock_build_service.return_value
        mock_service.generate.return_value = self.output_json
        session = Session.objects.create(owner=self.user, title="Existing Session")
        self.client.force_authenticate(user=self.user)

        first_response = self.client.post(
            "/llm/generate/",
            {
                "input_json": {"filename": "invoice.pdf", "extracted": "raw upload text"},
                "session_id": str(session.id),
            },
            format="json",
        )
        second_response = self.client.post(
            "/llm/generate/",
            {
                "input_json": {"filename": "invoice-2.pdf", "extracted": "raw upload text 2"},
                "session_id": str(session.id),
            },
            format="json",
        )

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 200)
        self.assertEqual(GeneratedOutput.objects.filter(session=session).count(), 2)

    @patch("llm.views.create_generated_output")
    @patch("llm.views.build_llm_generation_service")
    def test_llm_generate_returns_500_and_rolls_back_when_output_persistence_fails(
        self, mock_build_service, mock_create_generated_output
    ):
        mock_service = mock_build_service.return_value
        mock_service.generate.return_value = self.output_json
        mock_create_generated_output.side_effect = RuntimeError("db write failed")
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/llm/generate/",
            {"input_json": {"filename": "invoice.pdf", "extracted": "raw upload text"}},
            format="json",
        )

        self.assertEqual(response.status_code, 500)
        self.assertFalse(Session.objects.exists())
        self.assertFalse(GeneratedOutput.objects.exists())

    @patch("llm.views.build_llm_generation_service")
    def test_llm_generate_returns_404_for_unknown_owned_session_id(self, mock_build_service):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/llm/generate/",
            {
                "input_json": {"filename": "invoice.pdf", "extracted": "raw upload text"},
                "session_id": str(uuid4()),
            },
            format="json",
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data["detail"], "Session not found.")
        mock_build_service.assert_not_called()
        self.assertFalse(Session.objects.exists())
        self.assertFalse(GeneratedOutput.objects.exists())

    @patch("llm.views.build_llm_generation_service")
    def test_llm_generate_returns_404_for_session_owned_by_other_user(self, mock_build_service):
        other_user = User.objects.create_user(
            email="other-session-owner@example.com",
            name="Other Owner",
            password="secret",
            status="verified",
        )
        foreign_session = Session.objects.create(owner=other_user, title="Foreign Session")
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/llm/generate/",
            {
                "input_json": {"filename": "invoice.pdf", "extracted": "raw upload text"},
                "session_id": str(foreign_session.id),
            },
            format="json",
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data["detail"], "Session not found.")
        mock_build_service.assert_not_called()
        self.assertEqual(Session.objects.count(), 1)
        self.assertFalse(GeneratedOutput.objects.exists())

class ThinkingLogEndpointTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.verified_user = User.objects.create_user(
            email="thinking-log-owner@example.com",
            name="Thinking Log Owner",
            password="secret",
            status="verified",
        )
        self.unverified_user = User.objects.create_user(
            email="thinking-log-unverified@example.com",
            name="Thinking Log Unverified",
            password="secret",
            status="unverified",
        )
        self.other_user = User.objects.create_user(
            email="thinking-log-other@example.com",
            name="Thinking Log Other",
            password="secret",
            status="verified",
        )

    def _create_chat_message(self, owner, *, session=None, thinking_log, role="assistant"):
        session = session or Session.objects.create(owner=owner, title="Thinking Log Session")
        return ChatMessage.objects.create(
            session=session,
            role=role,
            content="Thinking log message.",
            thinking_log=thinking_log,
            created_at=timezone.now(),
        )

    def test_thinking_log_list_returns_filtered_records_for_owner(self):
        owned_session = Session.objects.create(owner=self.verified_user, title="Owned Session")
        other_session = Session.objects.create(owner=self.other_user, title="Other Session")

        owned_match = self._create_chat_message(
            self.verified_user,
            session=owned_session,
            thinking_log="Mapped invoice total to total_amount.",
        )
        self._create_chat_message(
            self.verified_user,
            session=Session.objects.create(owner=self.verified_user, title="Owned Session 2"),
            thinking_log="Validated header consistency.",
        )
        self._create_chat_message(
            self.other_user,
            session=other_session,
            thinking_log="Other user log.",
        )

        self.client.force_authenticate(user=self.verified_user)
        response = self.client.get(f"/llm/thinking-logs/?session_id={owned_session.id}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["page"], 1)
        self.assertEqual(response.data["page_size"], 10)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["id"], str(owned_match.id))
        self.assertEqual(response.data["results"][0]["session_id"], str(owned_session.id))
        self.assertEqual(response.data["results"][0]["chat_id"], str(owned_match.id))
        self.assertIsNone(response.data["results"][0]["request_id"])

    def test_thinking_log_list_filters_by_chat_id_without_session_filter(self):
        matched_session = Session.objects.create(owner=self.verified_user, title="Matched Session")
        matched = self._create_chat_message(
            self.verified_user,
            session=matched_session,
            thinking_log="Request filtered record.",
        )
        self._create_chat_message(
            self.verified_user,
            session=Session.objects.create(owner=self.verified_user, title="Other Owned Session"),
            thinking_log="Non matching request.",
        )
        self._create_chat_message(
            self.other_user,
            session=Session.objects.create(owner=self.other_user, title="Other User Session"),
            thinking_log="Other owner record.",
        )

        self.client.force_authenticate(user=self.verified_user)
        response = self.client.get(f"/llm/thinking-logs/?chat_id={matched.id}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["id"], str(matched.id))
        self.assertEqual(response.data["results"][0]["chat_id"], str(matched.id))

    def test_thinking_log_list_filters_by_request_id_for_backward_compatibility(self):
        matched_session = Session.objects.create(owner=self.verified_user, title="Matched Session")
        matched = self._create_chat_message(
            self.verified_user,
            session=matched_session,
            thinking_log="Request ID filtered record.",
        )
        self._create_chat_message(
            self.verified_user,
            session=Session.objects.create(owner=self.verified_user, title="Other Owned Session"),
            thinking_log="Non matching request.",
        )
        self._create_chat_message(
            self.other_user,
            session=Session.objects.create(owner=self.other_user, title="Other User Session"),
            thinking_log="Other owner record.",
        )

        self.client.force_authenticate(user=self.verified_user)
        response = self.client.get(f"/llm/thinking-logs/?request_id={matched.id}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["id"], str(matched.id))

    def test_thinking_log_list_without_filters_returns_all_owned_records(self):
        owned_session_1 = Session.objects.create(owner=self.verified_user, title="Owned A")
        owned_session_2 = Session.objects.create(owner=self.verified_user, title="Owned B")
        other_session = Session.objects.create(owner=self.other_user, title="Other C")

        self._create_chat_message(
            self.verified_user,
            session=owned_session_1,
            thinking_log="Owned record A.",
        )
        self._create_chat_message(
            self.verified_user,
            session=owned_session_2,
            thinking_log="Owned record B.",
        )
        self._create_chat_message(
            self.other_user,
            session=other_session,
            thinking_log="Other owner record.",
        )

        self.client.force_authenticate(user=self.verified_user)
        response = self.client.get("/llm/thinking-logs/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 2)
        self.assertEqual(len(response.data["results"]), 2)

    def test_thinking_log_detail_returns_record_for_owner(self):
        session = Session.objects.create(owner=self.verified_user, title="Detail Session")
        record = self._create_chat_message(
            self.verified_user,
            session=session,
            thinking_log="Normalization notes for numeric columns.",
        )

        self.client.force_authenticate(user=self.verified_user)
        response = self.client.get(f"/llm/thinking-logs/{record.id}/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], str(record.id))
        self.assertEqual(response.data["session_id"], str(session.id))
        self.assertEqual(response.data["chat_id"], str(record.id))
        self.assertIsNone(response.data["request_id"])
        self.assertEqual(
            response.data["thinking_log"],
            "Normalization notes for numeric columns.",
        )

    def test_thinking_log_detail_returns_404_when_not_found(self):
        self.client.force_authenticate(user=self.verified_user)

        response = self.client.get("/llm/thinking-logs/00000000-0000-0000-0000-000000000000/")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data, {"detail": "Thinking log not found."})

    def test_thinking_log_detail_blocks_access_to_other_user_record(self):
        foreign_session = Session.objects.create(owner=self.other_user, title="Foreign Session")
        foreign_record = self._create_chat_message(
            self.other_user,
            session=foreign_session,
            thinking_log="Foreign record.",
        )
        self.client.force_authenticate(user=self.verified_user)

        response = self.client.get(f"/llm/thinking-logs/{foreign_record.id}/")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data, {"detail": "Thinking log not found."})

    def test_thinking_log_detail_returns_404_for_empty_thinking_log_record(self):
        session = Session.objects.create(owner=self.verified_user, title="Empty Log Session")
        empty_log_record = self._create_chat_message(
            self.verified_user,
            session=session,
            thinking_log="",
        )

        self.client.force_authenticate(user=self.verified_user)
        response = self.client.get(f"/llm/thinking-logs/{empty_log_record.id}/")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data, {"detail": "Thinking log not found."})

    def test_thinking_log_list_supports_large_dataset_pagination(self):
        bulk_session = Session.objects.create(owner=self.verified_user, title="Bulk Session")
        for index in range(25):
            self._create_chat_message(
                self.verified_user,
                session=bulk_session,
                thinking_log=f"Summary item {index}",
            )

        self.client.force_authenticate(user=self.verified_user)
        response = self.client.get(f"/llm/thinking-logs/?session_id={bulk_session.id}&page=2&page_size=10")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 25)
        self.assertEqual(response.data["page"], 2)
        self.assertEqual(response.data["page_size"], 10)
        self.assertEqual(len(response.data["results"]), 10)

    def test_thinking_log_list_requires_authentication(self):
        response = self.client.get("/llm/thinking-logs/")

        self.assertEqual(response.status_code, 401)

    def test_thinking_log_list_returns_403_for_authenticated_unverified_user(self):
        self.client.force_authenticate(user=self.unverified_user)

        response = self.client.get("/llm/thinking-logs/")

        self.assertEqual(response.status_code, 403)

    def test_thinking_log_list_error_schema_is_consistent_for_invalid_pagination(self):
        self.client.force_authenticate(user=self.verified_user)

        response = self.client.get("/llm/thinking-logs/?page=0&page_size=10")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["detail"], "Invalid request payload.")
        self.assertEqual(
            response.data["errors"],
            {"pagination": ["Invalid thinking log pagination request."]},
        )

    def test_thinking_log_list_rejects_page_size_above_maximum(self):
        self.client.force_authenticate(user=self.verified_user)

        response = self.client.get("/llm/thinking-logs/?page_size=101")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["detail"], "Invalid request payload.")
        self.assertEqual(
            response.data["errors"],
            {"pagination": ["Invalid thinking log pagination request."]},
        )

    def test_thinking_log_list_rejects_invalid_chat_id(self):
        self.client.force_authenticate(user=self.verified_user)

        response = self.client.get("/llm/thinking-logs/?chat_id=not-a-uuid")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["detail"], "Invalid request payload.")
        self.assertEqual(
            response.data["errors"],
            {"chat_id": ["Invalid thinking log identifier."]},
        )

    def test_thinking_log_list_rejects_invalid_request_id(self):
        self.client.force_authenticate(user=self.verified_user)

        response = self.client.get("/llm/thinking-logs/?request_id=not-a-uuid")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["detail"], "Invalid request payload.")
        self.assertEqual(
            response.data["errors"],
            {"request_id": ["Invalid thinking log identifier."]},
        )

class SendMessagePositiveTest(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="send-msg-pos@example.com",
            name="Send Message User",
            password="secret",
            status="verified",
        )

    @patch("llm.views.generate_chat_response")
    def test_send_message_returns_200_with_reply_and_session_id(self, mock_generate):
        mock_generate.return_value = "Halo! Ada yang bisa saya bantu?"
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/llm/send-message/",
            {"message": "Halo"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["reply"], "Halo! Ada yang bisa saya bantu?")
        self.assertIn("session_id", response.data)
        self.assertIsNotNone(response.data["session_id"])

    @patch("llm.views.generate_chat_response")
    def test_send_message_creates_new_session_when_no_session_id_given(self, mock_generate):
        mock_generate.return_value = "ok"
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/llm/send-message/",
            {"message": "Halo"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        session_id = response.data["session_id"]
        self.assertTrue(Session.objects.filter(id=session_id, owner=self.user).exists())

    @patch("llm.views.generate_chat_response")
    def test_send_message_continues_existing_session(self, mock_generate):
        mock_generate.return_value = "Balasan lanjutan."
        session = Session.objects.create(owner=self.user)
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/llm/send-message/",
            {"session_id": str(session.id), "message": "Pesan lanjutan"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(str(response.data["session_id"]), str(session.id))

    @patch("llm.views.generate_chat_response")
    def test_send_message_persists_user_and_assistant_messages(self, mock_generate):
        mock_generate.return_value = "Balasan dari AI."
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/llm/send-message/",
            {"message": "Halo dari user"},
            format="json",
        )

        session_id = response.data["session_id"]
        messages = list(
            ChatMessage.objects.filter(session_id=session_id).order_by("created_at")
        )
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0].role, ChatMessage.ROLE_USER)
        self.assertEqual(messages[0].content, "Halo dari user")
        self.assertEqual(messages[1].role, ChatMessage.ROLE_ASSISTANT)
        self.assertEqual(messages[1].content, "Balasan dari AI.")

    @patch("llm.views.generate_chat_response")
    def test_send_message_passes_full_history_to_llm(self, mock_generate):
        mock_generate.return_value = "Balasan baru."
        session = Session.objects.create(owner=self.user)
        ChatMessage.objects.create(
            session=session, role=ChatMessage.ROLE_USER, content="Pesan pertama"
        )
        ChatMessage.objects.create(
            session=session, role=ChatMessage.ROLE_ASSISTANT, content="Balasan pertama"
        )
        self.client.force_authenticate(user=self.user)

        self.client.post(
            "/llm/send-message/",
            {"session_id": str(session.id), "message": "Pesan kedua"},
            format="json",
        )

        mock_generate.assert_called_once_with([
            {"role": "user", "content": "Pesan pertama"},
            {"role": "assistant", "content": "Balasan pertama"},
            {"role": "user", "content": "Pesan kedua"},
        ])

    @patch("llm.views.SendMessageResponseSerializer")
    @patch("llm.views.generate_chat_response")
    def test_send_message_returns_502_when_response_serializer_invalid(
        self, mock_generate, mock_serializer_class
    ):
        mock_generate.return_value = "reply text"
        mock_serializer_class.return_value.is_valid.return_value = False
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/llm/send-message/",
            {"message": "Halo"},
            format="json",
        )

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.data["detail"], "Failed to generate response from LLM provider.")


class SendMessageNegativeTest(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="send-msg-neg@example.com",
            name="Negative Test User",
            password="secret",
            status="verified",
        )

    def test_send_message_requires_authentication(self):
        response = self.client.post(
            "/llm/send-message/",
            {"message": "Halo"},
            format="json",
        )

        self.assertEqual(response.status_code, 401)

    @patch("llm.views.generate_chat_response")
    def test_send_message_returns_404_for_unknown_session_id(self, mock_generate):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/llm/send-message/",
            {"session_id": str(uuid4()), "message": "Halo"},
            format="json",
        )

        self.assertEqual(response.status_code, 404)
        mock_generate.assert_not_called()

    @patch("llm.views.generate_chat_response")
    def test_send_message_returns_404_for_session_owned_by_other_user(self, mock_generate):
        other_user = User.objects.create_user(
            email="other-user@example.com",
            name="Other User",
            password="secret",
            status="verified",
        )
        other_session = Session.objects.create(owner=other_user)
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/llm/send-message/",
            {"session_id": str(other_session.id), "message": "Halo"},
            format="json",
        )

        self.assertEqual(response.status_code, 404)
        mock_generate.assert_not_called()

    @patch("llm.views.generate_chat_response")
    def test_send_message_rejects_empty_payload(self, mock_generate):
        self.client.force_authenticate(user=self.user)

        response = self.client.post("/llm/send-message/", {}, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["detail"], "Invalid request payload.")
        self.assertIn("errors", response.data)
        mock_generate.assert_not_called()

    @patch("llm.views.generate_chat_response")
    def test_send_message_rejects_missing_message(self, mock_generate):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/llm/send-message/",
            {"session_id": str(uuid4())},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["detail"], "Invalid request payload.")
        self.assertIn("message", response.data["errors"])
        mock_generate.assert_not_called()

    @patch("llm.views.generate_chat_response")
    def test_send_message_rejects_blank_message(self, mock_generate):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/llm/send-message/",
            {"message": ""},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("message", response.data["errors"])
        mock_generate.assert_not_called()

    @patch("llm.views.generate_chat_response")
    def test_send_message_rejects_whitespace_only_message(self, mock_generate):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/llm/send-message/",
            {"message": "   "},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("message", response.data["errors"])
        mock_generate.assert_not_called()

    @patch("llm.views.generate_chat_response")
    def test_send_message_rejects_invalid_session_id_format(self, mock_generate):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/llm/send-message/",
            {"session_id": "not-a-valid-UUID", "message": "Halo"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["detail"], "Invalid request payload.")
        self.assertIn("session_id", response.data["errors"])
        mock_generate.assert_not_called()

    def test_send_message_rejects_non_json_content_type(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/llm/send-message/",
            data="plain text",
            content_type="text/plain",
        )

        self.assertEqual(response.status_code, 415)
        self.assertEqual(response.data["detail"], "Content-Type must be application/json.")

    def test_send_message_rejects_get_method(self):
        response = self.client.get("/llm/send-message/")

        self.assertEqual(response.status_code, 405)


class SendMessageErrorHandlingTest(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="send-msg-err@example.com",
            name="Error Test User",
            password="secret",
            status="verified",
        )

    @patch("llm.views.generate_chat_response")
    def test_send_message_returns_503_when_openai_not_configured(self, mock_generate):
        mock_generate.side_effect = OpenAIConfigurationError("OPENAI_API_KEY is not configured.")
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/llm/send-message/",
            {"message": "Halo"},
            format="json",
        )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data["detail"], "Service unavailable. Please try again later.")

    @patch("llm.views.generate_chat_response")
    def test_send_message_returns_502_for_openai_service_error(self, mock_generate):
        mock_generate.side_effect = OpenAIServiceError("OpenAI response did not include a reply.")
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/llm/send-message/",
            {"message": "Halo"},
            format="json",
        )

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.data["detail"], "Failed to generate response from LLM provider.")

    @patch("llm.views.generate_chat_response")
    def test_send_message_returns_502_for_upstream_auth_error(self, mock_generate):
        mock_generate.side_effect = OpenAIUpstreamError("LLM authentication failed.", status_code=502)
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/llm/send-message/",
            {"message": "Halo"},
            format="json",
        )

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.data["detail"], "Failed to generate response from LLM provider.")

    @patch("llm.views.generate_chat_response")
    def test_send_message_returns_429_for_upstream_rate_limit(self, mock_generate):
        mock_generate.side_effect = OpenAIUpstreamError("LLM rate limit exceeded.", status_code=429)
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/llm/send-message/",
            {"message": "Halo"},
            format="json",
        )

        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.data["detail"], "Failed to generate response from LLM provider.")

    @patch("llm.views.generate_chat_response")
    def test_send_message_returns_504_for_upstream_timeout(self, mock_generate):
        mock_generate.side_effect = OpenAIUpstreamError("LLM request timed out.", status_code=504)
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/llm/send-message/",
            {"message": "Halo"},
            format="json",
        )

        self.assertEqual(response.status_code, 504)
        self.assertEqual(response.data["detail"], "Failed to generate response from LLM provider.")

    @patch("llm.views.logger")
    @patch("llm.views.generate_chat_response")
    def test_send_message_returns_500_for_unexpected_error(self, mock_generate, mock_logger):
        mock_generate.side_effect = RuntimeError("unexpected failure")
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/llm/send-message/",
            {"message": "Halo"},
            format="json",
        )

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.data["detail"], "Internal server error.")
        mock_logger.exception.assert_called_once()

    @patch("llm.views.generate_chat_response")
    def test_send_message_does_not_expose_upstream_error_details(self, mock_generate):
        mock_generate.side_effect = OpenAIUpstreamError("raw upstream details", status_code=502)
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/llm/send-message/",
            {"message": "Halo"},
            format="json",
        )

        self.assertEqual(response.status_code, 502)
        self.assertNotIn("raw upstream details", str(response.data))


class SendMessageEdgeCaseTest(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="send-msg-edge@example.com",
            name="Edge Case User",
            password="secret",
            status="verified",
        )

    @patch("llm.views.generate_chat_response")
    def test_send_message_at_max_length_is_accepted(self, mock_generate):
        mock_generate.return_value = "ok"
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/llm/send-message/",
            {"message": "a" * MAX_MESSAGE_LENGTH},
            format="json",
        )

        self.assertEqual(response.status_code, 200)

    @patch("llm.views.generate_chat_response")
    def test_send_message_exceeding_max_length_is_rejected(self, mock_generate):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/llm/send-message/",
            {"message": "a" * (MAX_MESSAGE_LENGTH + 1)},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["detail"], "Invalid request payload.")
        self.assertIn("message", response.data["errors"])
        mock_generate.assert_not_called()

    @patch("llm.views.build_history_with_summary")
    @patch("llm.views.generate_chat_response")
    def test_send_message_passes_summary_history_to_llm(self, mock_generate, mock_build_summary):
        mock_generate.return_value = "reply"
        summarized_history = [
            {"role": "system", "content": "[Summary of earlier conversation]: Old context."},
            {"role": "user", "content": "new msg"},
        ]
        mock_build_summary.return_value = summarized_history
        session = Session.objects.create(owner=self.user)
        self.client.force_authenticate(user=self.user)

        self.client.post(
            "/llm/send-message/",
            {"session_id": str(session.id), "message": "new msg"},
            format="json",
        )

        mock_build_summary.assert_called_once()
        mock_generate.assert_called_once_with(summarized_history)
