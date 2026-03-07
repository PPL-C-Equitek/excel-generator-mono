from django.test import SimpleTestCase
from django.core.cache import cache
from rest_framework.test import APIClient
from unittest.mock import patch

from llm.services.openai_client import OpenAIConfigurationError, OpenAIServiceError


class LlmGenerateEndpointTest(SimpleTestCase):
    def setUp(self):
        super().setUp()
        cache.clear()

    @patch("llm.views.generate_json")
    def test_llm_generate_returns_200(self, mock_generate_json):
        mock_generate_json.return_value = {"status": "ok"}
        client = APIClient()

        payload = {"input_json": {"sheet": "Sheet1"}}
        response = client.post("/llm/generate/", payload, format="json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["output_json"], {"status": "ok"})
        mock_generate_json.assert_called_once_with(input_json={"sheet": "Sheet1"})

    def test_llm_generate_rejects_missing_input_json(self):
        client = APIClient()
        response = client.post("/llm/generate/", {}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["detail"], "Invalid request payload.")

    def test_llm_generate_rejects_non_object_or_array_input_json(self):
        client = APIClient()
        response = client.post("/llm/generate/", {"input_json": "not-json-object"}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["detail"], "Invalid request payload.")

    def test_llm_generate_rejects_client_model_field(self):
        client = APIClient()
        response = client.post(
            "/llm/generate/",
            {"input_json": {"ok": True}, "model": "gpt-4.1-mini"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["detail"], "Invalid request payload.")

    @patch("llm.views.generate_json")
    def test_llm_generate_returns_503_for_service_error(self, mock_generate_json):
        mock_generate_json.side_effect = OpenAIConfigurationError("OPENAI_API_KEY is not configured.")
        client = APIClient()

        response = client.post("/llm/generate/", {"input_json": {"hello": "world"}}, format="json")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data["detail"], "Service unavailable. Please try again later.")

    @patch("llm.views.generate_json")
    def test_llm_generate_returns_502_for_invalid_json_response(self, mock_generate_json):
        mock_generate_json.side_effect = OpenAIServiceError("OpenAI response is not valid JSON.")
        client = APIClient()

        response = client.post("/llm/generate/", {"input_json": {"hello": "world"}}, format="json")

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.data["detail"], "Failed to generate response from OpenAI.")

    @patch("llm.views.logger")
    @patch("llm.views.generate_json")
    def test_llm_generate_returns_502_for_unexpected_error(self, mock_generate_json, mock_logger):
        mock_generate_json.side_effect = RuntimeError("upstream error")
        client = APIClient()

        response = client.post("/llm/generate/", {"input_json": {"hello": "world"}}, format="json")

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.data["detail"], "Failed to generate response from OpenAI.")
        mock_logger.exception.assert_called_once()

    @patch("llm.views.LlmGenerateResponseSerializer")
    @patch("llm.views.generate_json")
    def test_llm_generate_returns_502_when_response_serializer_invalid(
        self, mock_generate_json, mock_response_serializer_class
    ):
        mock_generate_json.return_value = {"status": "ok"}
        mock_response_serializer = mock_response_serializer_class.return_value
        mock_response_serializer.is_valid.return_value = False
        client = APIClient()

        response = client.post("/llm/generate/", {"input_json": {"hello": "world"}}, format="json")

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.data["detail"], "Failed to generate response from OpenAI.")
        mock_response_serializer_class.assert_called_once_with(data={"output_json": {"status": "ok"}})

    @patch("llm.views.generate_json")
    def test_llm_generate_returns_400_for_value_error(self, mock_generate_json):
        mock_generate_json.side_effect = ValueError("input_json must be an object or array.")
        client = APIClient()

        response = client.post("/llm/generate/", {"input_json": {"hello": "world"}}, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["detail"], "Invalid request payload.")

    def test_llm_generate_rejects_get(self):
        client = APIClient()
        response = client.get("/llm/generate/")
        self.assertEqual(response.status_code, 405)

    @patch("llm.views.generate_json")
    def test_llm_generate_rate_limited_5_per_minute(self, mock_generate_json):
        mock_generate_json.return_value = {"status": "ok"}
        client = APIClient()
        payload = {"input_json": {"hello": "world"}}

        for _ in range(5):
            response = client.post("/llm/generate/", payload, format="json", REMOTE_ADDR="127.0.0.99")
            self.assertEqual(response.status_code, 200)

        blocked = client.post("/llm/generate/", payload, format="json", REMOTE_ADDR="127.0.0.99")
        self.assertEqual(blocked.status_code, 429)
        self.assertIn("detail", blocked.data)
        self.assertEqual(blocked["X-RateLimit-Limit"], "5")

