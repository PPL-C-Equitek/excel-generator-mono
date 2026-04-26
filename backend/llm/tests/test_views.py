from types import SimpleNamespace

from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from unittest.mock import patch
from uuid import uuid4

from artifact_history.models import ArtifactHistory
from authentication.models import User
from chat_sessions.models import ChatMessage, Session
from llm.services.generation_service import CustomSchemaNotFoundError
from llm.services.openai_client import OpenAITextGenerationProvider
from llm.services.openai_client import (
    OpenAIConfigurationError,
    OpenAIServiceError,
    OpenAIUpstreamError,
)
from llm.views import (
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

    @patch("llm.views.build_llm_generation_service")
    def test_llm_generate_returns_200(self, mock_build_service):
        mock_service = mock_build_service.return_value
        mock_service.generate.return_value = {"status": "ok"}
        client = APIClient()

        payload = {
            "input_json": {"sheet": "Sheet1"},
            "refinement": {"enabled": False},
        }
        response = client.post("/llm/generate/", payload, format="json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["output_json"], {"status": "ok"})
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
            {
                "input_json": {"sheet": "Sheet1"},
                "refinement": {"enabled": False},
            },
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
            {
                "input_json": {"sheet": "Sheet1"},
                "refinement": {"enabled": False},
            },
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
            {
                "input_json": {"sheet": "Sheet1"},
                "refinement": {"enabled": False},
            },
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
            {
                "input_json": {"sheet": "Sheet1"},
                "custom_schema_id": str(schema_id),
                "refinement": {"enabled": False},
            },
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
            {
                "input_json": {"sheet": "Sheet1"},
                "custom_schema_id": str(schema_id),
                "refinement": {"enabled": False},
            },
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

    def test_llm_generate_rejects_refinement_max_iterations_above_cap(self):
        client = APIClient()
        response = client.post(
            "/llm/generate/",
            {
                "input_json": {"sheet": "Sheet1"},
                "refinement": {"enabled": True, "max_iterations": 4},
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["detail"], "Invalid request payload.")
        self.assertIn("errors", response.data)

    @patch("llm.views.RefinementOrchestrator")
    @patch("llm.views.build_llm_generation_service")
    def test_llm_generate_with_refinement_returns_extended_fields(
        self,
        mock_build_generation_service,
        mock_refinement_orchestrator_class,
    ):
        mock_build_generation_service.return_value = SimpleNamespace()
        mock_refinement_orchestrator = mock_refinement_orchestrator_class.return_value
        mock_refinement_orchestrator.run.return_value = {
            "raw_json": {"status": "raw"},
            "validated_json": {
                "document_info": {"source_type": "Excel", "filename": "sample.xlsx"},
                "summary": {"total_tables": 1},
                "content_data": [
                    {
                        "table_name": "Sheet1",
                        "headers": ["name"],
                        "rows": [{"name": "A"}],
                    }
                ],
            },
            "output_json": {
                "document_info": {"source_type": "Excel", "filename": "sample.xlsx"},
                "summary": {"total_tables": 1},
                "content_data": [
                    {
                        "table_name": "Sheet1",
                        "headers": ["name"],
                        "rows": [{"name": "A"}],
                    }
                ],
            },
            "validation_log": {
                "iteration": 2,
                "verdict": "valid",
                "errors": [],
                "warnings": [],
                "summary": "Output passed strict export schema validation.",
            },
            "reasoning": {
                "final_answer": "Refinement completed.",
                "reasoning_steps": ["Fixed required keys."],
                "thinking_log": "Iterative repair completed.",
            },
            "refinement_meta": {
                "iterations_run": 2,
                "max_iterations": 3,
                "early_exit_triggered": True,
                "final_status": "valid",
            },
        }
        client = APIClient()

        response = client.post(
            "/llm/generate/",
            {
                "input_json": {"sheet": "Sheet1"},
                "refinement": {
                    "enabled": True,
                    "max_iterations": 3,
                    "early_exit_on_valid": True,
                },
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["output_json"], response.data["validated_json"])
        self.assertNotIn("raw_json", response.data)
        self.assertNotIn("validation_log", response.data)
        self.assertNotIn("refinement_meta", response.data)
        self.assertEqual(response.data["reasoning"]["final_answer"], "Refinement completed.")

    @override_settings(LLM_EXPOSE_VALIDATION_LOG=False)
    @patch("llm.views.RefinementOrchestrator")
    @patch("llm.views.build_llm_generation_service")
    def test_llm_generate_with_refinement_hides_debug_refinement_fields_when_flag_disabled(
        self,
        mock_build_generation_service,
        mock_refinement_orchestrator_class,
    ):
        mock_build_generation_service.return_value = SimpleNamespace()
        mock_refinement_orchestrator = mock_refinement_orchestrator_class.return_value
        mock_refinement_orchestrator.run.return_value = {
            "raw_json": {"status": "raw"},
            "validated_json": {"status": "validated"},
            "output_json": {"status": "validated"},
            "validation_log": {
                "iteration": 1,
                "verdict": "valid",
                "errors": [],
                "warnings": [],
                "summary": "Output passed strict export schema validation.",
            },
            "reasoning": None,
            "refinement_meta": {
                "iterations_run": 1,
                "max_iterations": 3,
                "early_exit_triggered": True,
                "final_status": "valid",
            },
        }
        client = APIClient()

        response = client.post(
            "/llm/generate/",
            {"input_json": {"sheet": "Sheet1"}, "refinement": {"enabled": True}},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["output_json"], {"status": "validated"})
        self.assertEqual(response.data["validated_json"], {"status": "validated"})
        self.assertNotIn("raw_json", response.data)
        self.assertNotIn("validation_log", response.data)
        self.assertNotIn("refinement_meta", response.data)

    @override_settings(LLM_EXPOSE_VALIDATION_LOG=True)
    @patch("llm.views.RefinementOrchestrator")
    @patch("llm.views.build_llm_generation_service")
    def test_llm_generate_with_refinement_exposes_validation_log_when_enabled(
        self,
        mock_build_generation_service,
        mock_refinement_orchestrator_class,
    ):
        mock_build_generation_service.return_value = SimpleNamespace()
        mock_refinement_orchestrator = mock_refinement_orchestrator_class.return_value
        mock_refinement_orchestrator.run.return_value = {
            "raw_json": {"status": "raw"},
            "validated_json": {
                "document_info": {"source_type": "Excel", "filename": "sample.xlsx"},
                "summary": {"total_tables": 1},
                "content_data": [
                    {
                        "table_name": "Sheet1",
                        "headers": ["name"],
                        "rows": [{"name": "A"}],
                    }
                ],
            },
            "output_json": {
                "document_info": {"source_type": "Excel", "filename": "sample.xlsx"},
                "summary": {"total_tables": 1},
                "content_data": [
                    {
                        "table_name": "Sheet1",
                        "headers": ["name"],
                        "rows": [{"name": "A"}],
                    }
                ],
            },
            "validation_log": {
                "iteration": 2,
                "verdict": "valid",
                "errors": [],
                "warnings": [],
                "summary": "Output passed strict export schema validation.",
            },
            "reasoning": {
                "final_answer": "Refinement completed.",
                "reasoning_steps": ["Fixed required keys."],
                "thinking_log": "Iterative repair completed.",
            },
            "refinement_meta": {
                "iterations_run": 2,
                "max_iterations": 3,
                "early_exit_triggered": True,
                "final_status": "valid",
            },
        }
        client = APIClient()

        response = client.post(
            "/llm/generate/",
            {
                "input_json": {"sheet": "Sheet1"},
                "refinement": {
                    "enabled": True,
                    "max_iterations": 3,
                    "early_exit_on_valid": True,
                },
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["raw_json"], {"status": "raw"})
        self.assertEqual(response.data["validation_log"]["verdict"], "valid")
        self.assertEqual(response.data["refinement_meta"]["final_status"], "valid")

    # Positive
    @override_settings(LLM_EXPOSE_VALIDATION_LOG=True)
    @patch("llm.views.RefinementOrchestrator")
    @patch("llm.views.build_llm_generation_service")
    def test_positive_llm_generate_exposes_debug_refinement_fields_when_flag_enabled(
        self,
        mock_build_generation_service,
        mock_refinement_orchestrator_class,
    ):
        mock_build_generation_service.return_value = SimpleNamespace()
        mock_refinement_orchestrator = mock_refinement_orchestrator_class.return_value
        mock_refinement_orchestrator.run.return_value = {
            "raw_json": {"status": "raw"},
            "validated_json": {"status": "validated"},
            "output_json": {"status": "validated"},
            "validation_log": {
                "iteration": 1,
                "verdict": "valid",
                "errors": [],
                "warnings": [],
                "summary": "Output passed strict export schema validation.",
            },
            "reasoning": {
                "final_answer": "ok",
                "reasoning_steps": ["step"],
                "thinking_log": "log",
            },
            "refinement_meta": {
                "iterations_run": 1,
                "max_iterations": 3,
                "early_exit_triggered": True,
                "final_status": "valid",
            },
        }
        client = APIClient()

        response = client.post(
            "/llm/generate/",
            {"input_json": {"sheet": "Sheet1"}, "refinement": {"enabled": True}},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("raw_json", response.data)
        self.assertIn("validation_log", response.data)
        self.assertIn("refinement_meta", response.data)

    # Negative
    def test_negative_llm_generate_rejects_invalid_refinement_shape(self):
        client = APIClient()
        response = client.post(
            "/llm/generate/",
            {
                "input_json": {"sheet": "Sheet1"},
                "refinement": {"max_iterations": "bad-value"},
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["detail"], "Invalid request payload.")
        self.assertIn("errors", response.data)

    # Edge
    @patch("llm.views.build_llm_generation_service")
    def test_edge_llm_generate_uses_non_refinement_path_when_refinement_explicitly_disabled(
        self,
        mock_build_service,
    ):
        mock_service = mock_build_service.return_value
        mock_service.generate.return_value = {"status": "ok"}
        client = APIClient()

        response = client.post(
            "/llm/generate/",
            {
                "input_json": {"sheet": "Sheet1"},
                "include_reasoning": False,
                "refinement": {"enabled": False},
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["output_json"], {"status": "ok"})
        self.assertNotIn("validated_json", response.data)
        self.assertNotIn("raw_json", response.data)

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

        response = client.post(
            "/llm/generate/",
            {
                "input_json": {"hello": "world"},
                "refinement": {"enabled": False},
            },
            format="json",
        )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data["detail"], "Service unavailable. Please try again later.")

    @patch("llm.views.build_llm_generation_service")
    def test_llm_generate_returns_502_for_invalid_json_response(self, mock_build_service):
        mock_service = mock_build_service.return_value
        mock_service.generate.side_effect = OpenAIServiceError(
            "OpenAI response is not valid JSON."
        )
        client = APIClient()

        response = client.post(
            "/llm/generate/",
            {
                "input_json": {"hello": "world"},
                "refinement": {"enabled": False},
            },
            format="json",
        )

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

        response = client.post(
            "/llm/generate/",
            {
                "input_json": {"hello": "world"},
                "refinement": {"enabled": False},
            },
            format="json",
        )

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

        response = client.post(
            "/llm/generate/",
            {
                "input_json": {"hello": "world"},
                "refinement": {"enabled": False},
            },
            format="json",
        )

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

        response = client.post(
            "/llm/generate/",
            {
                "input_json": {"hello": "world"},
                "refinement": {"enabled": False},
            },
            format="json",
        )

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.data["detail"], "Failed to generate response from LLM provider.")
        mock_response_serializer_class.assert_called_once_with(
            data={
                "output_json": {"status": "ok"},
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


class LlmGenerateHistoryIntegrationTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="history@example.com",
            name="History User",
            password="secret",
            status="verified",
        )

    @patch("llm.views.build_llm_generation_service")
    def test_llm_generate_persists_history_for_authenticated_user(self, mock_build_service):
        mock_service = mock_build_service.return_value
        output_json = {
            "document_info": {"filename": "invoice.pdf"},
            "summary": {"table_count": 1},
            "content_data": [{"table_name": "Sheet1", "headers": ["A"], "rows": [["1"]]}],
        }
        mock_service.generate.return_value = output_json
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
        self.assertEqual(ArtifactHistory.objects.count(), 1)
        history = ArtifactHistory.objects.get()
        self.assertEqual(history.owner, self.user)
        self.assertEqual(history.original_name, "invoice.pdf")
        self.assertEqual(history.custom_name, "")
        self.assertEqual(history.status_processing, "completed")
        self.assertEqual(history.output_json, output_json)

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
    def test_llm_generate_does_not_persist_history_when_generation_fails(
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
        self.assertFalse(ArtifactHistory.objects.exists())

    @patch("llm.views.build_llm_generation_service")
    def test_llm_generate_does_not_persist_history_for_anonymous_user(
        self, mock_build_service
    ):
        mock_service = mock_build_service.return_value
        mock_service.generate.return_value = {
            "document_info": {"filename": "invoice.pdf"},
            "summary": {"table_count": 1},
            "content_data": [{"table_name": "Sheet1", "headers": ["A"], "rows": [["1"]]}],
        }

        response = self.client.post(
            "/llm/generate/",
            {"input_json": {"filename": "invoice.pdf", "extracted": "raw upload text"}},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(ArtifactHistory.objects.exists())

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

    def _create_history(self, owner, *, session_id, request_id, thinking_log):
        return ArtifactHistory.objects.create(
            owner=owner,
            original_name="invoice.pdf",
            custom_name=None,
            output_json={
                "session_id": session_id,
                "request_id": request_id,
                "thinking_log": thinking_log,
                "summary": {"table_count": 1},
                "content_data": [
                    {"table_name": "Sheet1", "headers": ["A"], "rows": [["1"]]}
                ],
            },
            status_processing="completed",
            created_at=timezone.now(),
        )

    def test_thinking_log_list_returns_filtered_records_for_owner(self):
        owned_match = self._create_history(
            self.verified_user,
            session_id="session-1",
            request_id="request-a",
            thinking_log="Mapped invoice total to total_amount.",
        )
        self._create_history(
            self.verified_user,
            session_id="session-2",
            request_id="request-b",
            thinking_log="Validated header consistency.",
        )
        self._create_history(
            self.other_user,
            session_id="session-1",
            request_id="request-c",
            thinking_log="Other user log.",
        )

        self.client.force_authenticate(user=self.verified_user)
        response = self.client.get("/llm/thinking-logs/?session_id=session-1")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["page"], 1)
        self.assertEqual(response.data["page_size"], 10)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["id"], str(owned_match.id))
        self.assertEqual(response.data["results"][0]["session_id"], "session-1")
        self.assertEqual(response.data["results"][0]["request_id"], "request-a")

    def test_thinking_log_list_filters_by_request_id_without_session_filter(self):
        matched = self._create_history(
            self.verified_user,
            session_id="session-x",
            request_id="request-target",
            thinking_log="Request filtered record.",
        )
        self._create_history(
            self.verified_user,
            session_id="session-y",
            request_id="request-other",
            thinking_log="Non matching request.",
        )
        self._create_history(
            self.other_user,
            session_id="session-z",
            request_id="request-target",
            thinking_log="Other owner record.",
        )

        self.client.force_authenticate(user=self.verified_user)
        response = self.client.get("/llm/thinking-logs/?request_id=request-target")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["id"], str(matched.id))
        self.assertEqual(response.data["results"][0]["request_id"], "request-target")

    def test_thinking_log_list_without_filters_returns_all_owned_records(self):
        self._create_history(
            self.verified_user,
            session_id="session-a",
            request_id="request-a",
            thinking_log="Owned record A.",
        )
        self._create_history(
            self.verified_user,
            session_id="session-b",
            request_id="request-b",
            thinking_log="Owned record B.",
        )
        self._create_history(
            self.other_user,
            session_id="session-c",
            request_id="request-c",
            thinking_log="Other owner record.",
        )

        self.client.force_authenticate(user=self.verified_user)
        response = self.client.get("/llm/thinking-logs/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 2)
        self.assertEqual(len(response.data["results"]), 2)

    def test_thinking_log_detail_returns_record_for_owner(self):
        record = self._create_history(
            self.verified_user,
            session_id="session-9",
            request_id="request-z",
            thinking_log="Normalization notes for numeric columns.",
        )

        self.client.force_authenticate(user=self.verified_user)
        response = self.client.get(f"/llm/thinking-logs/{record.id}/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], str(record.id))
        self.assertEqual(response.data["session_id"], "session-9")
        self.assertEqual(response.data["request_id"], "request-z")
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
        foreign_record = self._create_history(
            self.other_user,
            session_id="session-foreign",
            request_id="request-foreign",
            thinking_log="Foreign record.",
        )
        self.client.force_authenticate(user=self.verified_user)

        response = self.client.get(f"/llm/thinking-logs/{foreign_record.id}/")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data, {"detail": "Thinking log not found."})

    def test_thinking_log_list_supports_large_dataset_pagination(self):
        for index in range(25):
            self._create_history(
                self.verified_user,
                session_id="session-bulk",
                request_id=f"req-{index}",
                thinking_log=f"Summary item {index}",
            )

        self.client.force_authenticate(user=self.verified_user)
        response = self.client.get("/llm/thinking-logs/?session_id=session-bulk&page=2&page_size=10")

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
