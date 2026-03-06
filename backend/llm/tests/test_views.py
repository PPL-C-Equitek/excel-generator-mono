from django.test import SimpleTestCase
from rest_framework.test import APIClient
from unittest.mock import patch

from llm.services.openai_client import OpenAIServiceError


class LlmGenerateEndpointTest(SimpleTestCase):
    @patch("llm.views.generate_json")
    def test_llm_generate_returns_200(self, mock_generate_json):
        mock_generate_json.return_value = {"status": "ok"}
        client = APIClient()

        payload = {"input_json": {"sheet": "Sheet1"}}
        response = client.post("/llm/generate/", payload, format="json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["output_json"], {"status": "ok"})
        mock_generate_json.assert_called_once_with(input_json={"sheet": "Sheet1"}, model=None)

    @patch("llm.views.generate_json")
    def test_llm_generate_accepts_custom_model(self, mock_generate_json):
        mock_generate_json.return_value = {"status": "ok", "model": "custom"}
        client = APIClient()

        response = client.post(
            "/llm/generate/",
            {"input_json": {"hello": "world"}, "model": "gpt-4.1-mini"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["output_json"], {"status": "ok", "model": "custom"})
        mock_generate_json.assert_called_once_with(input_json={"hello": "world"}, model="gpt-4.1-mini")

    def test_llm_generate_rejects_missing_input_json(self):
        client = APIClient()
        response = client.post("/llm/generate/", {}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("input_json", response.data)

    def test_llm_generate_rejects_non_object_or_array_input_json(self):
        client = APIClient()
        response = client.post("/llm/generate/", {"input_json": "not-json-object"}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("input_json", response.data)

    def test_llm_generate_rejects_invalid_model(self):
        client = APIClient()
        response = client.post("/llm/generate/", {"input_json": {"ok": True}, "model": ""}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("model", response.data)

    @patch("llm.views.generate_json")
    def test_llm_generate_returns_503_for_service_error(self, mock_generate_json):
        mock_generate_json.side_effect = OpenAIServiceError("OPENAI_API_KEY is not configured.")
        client = APIClient()

        response = client.post("/llm/generate/", {"input_json": {"hello": "world"}}, format="json")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data["detail"], "OPENAI_API_KEY is not configured.")

    @patch("llm.views.generate_json")
    def test_llm_generate_returns_502_for_invalid_json_response(self, mock_generate_json):
        mock_generate_json.side_effect = OpenAIServiceError("OpenAI response is not valid JSON.")
        client = APIClient()

        response = client.post("/llm/generate/", {"input_json": {"hello": "world"}}, format="json")

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.data["detail"], "OpenAI response is not valid JSON.")

    @patch("llm.views.generate_json")
    def test_llm_generate_returns_502_for_unexpected_error(self, mock_generate_json):
        mock_generate_json.side_effect = RuntimeError("upstream error")
        client = APIClient()

        response = client.post("/llm/generate/", {"input_json": {"hello": "world"}}, format="json")

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.data["detail"], "Failed to generate response from OpenAI.")

    def test_llm_generate_rejects_get(self):
        client = APIClient()
        response = client.get("/llm/generate/")
        self.assertEqual(response.status_code, 405)

