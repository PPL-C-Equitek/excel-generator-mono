from types import SimpleNamespace

from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient
from unittest.mock import patch
from uuid import uuid4

from artifact_history.models import ArtifactHistory
from authentication.models import User
from llm.services.generation_service import CustomSchemaNotFoundError
from llm.services.openai_client import OpenAITextGenerationProvider
from llm.services.openai_client import (
    OpenAIConfigurationError,
    OpenAIServiceError,
    OpenAIUpstreamError,
)
from llm.views import (
    build_llm_generation_service,
    extract_original_name,
    get_authenticated_user_id,
)


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

    @patch("llm.views.build_llm_generation_service")
    def test_llm_generate_returns_200(self, mock_build_service):
        mock_service = mock_build_service.return_value
        mock_service.generate.return_value = {"status": "ok"}
        client = APIClient()

        payload = {"input_json": {"sheet": "Sheet1"}}
        response = client.post("/llm/generate/", payload, format="json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["output_json"], {"status": "ok"})
        self.assertEqual(mock_build_service.call_count, 1)
        self.assertFalse(mock_build_service.call_args[0][0].is_authenticated)
        mock_service.generate.assert_called_once_with(
            input_json={"sheet": "Sheet1"},
            custom_schema_id=None,
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
    def test_llm_generate_returns_401_for_upstream_auth_error(self, mock_build_service, mock_logger):
        mock_service = mock_build_service.return_value
        mock_service.generate.side_effect = OpenAIUpstreamError(
            "LLM authentication failed.",
            status_code=401,
        )
        client = APIClient()

        response = client.post("/llm/generate/", {"input_json": {"hello": "world"}}, format="json")

        self.assertEqual(response.status_code, 401)
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

    @patch("llm.views.LlmGenerateResponseSerializer")
    @patch("llm.views.build_llm_generation_service")
    def test_llm_generate_returns_502_when_response_serializer_invalid(
        self, mock_build_service, mock_response_serializer_class
    ):
        mock_service = mock_build_service.return_value
        mock_service.generate.return_value = {"status": "ok"}
        mock_response_serializer = mock_response_serializer_class.return_value
        mock_response_serializer.is_valid.return_value = False
        client = APIClient()

        response = client.post("/llm/generate/", {"input_json": {"hello": "world"}}, format="json")

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.data["detail"], "Failed to generate response from LLM provider.")
        mock_response_serializer_class.assert_called_once_with(data={"output_json": {"status": "ok"}})

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
