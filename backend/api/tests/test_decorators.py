from django.core.cache import cache
from django.test import SimpleTestCase
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory
from unittest.mock import patch

from api.decorators import rate_limit


class RateLimitDecoratorTest(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        cache.clear()

    def tearDown(self):
        cache.clear()

    def _build_view(self, max_requests=2, per="minute"):
        @api_view(["GET"])
        @rate_limit(max_requests=max_requests, per=per)
        def limited_view(request):
            return Response({"ok": True})

        return limited_view

    def test_allows_requests_within_limit(self):
        view = self._build_view(max_requests=2, per="minute")

        request_1 = self.factory.get("/limited/")
        request_1.META["REMOTE_ADDR"] = "127.0.0.1"
        response_1 = view(request_1)
        self.assertEqual(response_1.status_code, 200)
        self.assertEqual(response_1["X-RateLimit-Limit"], "2")
        self.assertEqual(response_1["X-RateLimit-Remaining"], "1")

        request_2 = self.factory.get("/limited/")
        request_2.META["REMOTE_ADDR"] = "127.0.0.1"
        response_2 = view(request_2)
        self.assertEqual(response_2.status_code, 200)
        self.assertEqual(response_2["X-RateLimit-Remaining"], "0")

    @patch("api.decorators.monotonic", side_effect=[10, 10])
    def test_blocks_request_after_limit(self, _mock_time):
        view = self._build_view(max_requests=1, per="minute")

        first = self.factory.get("/limited/")
        first.META["REMOTE_ADDR"] = "10.0.0.1"
        self.assertEqual(view(first).status_code, 200)

        second = self.factory.get("/limited/")
        second.META["REMOTE_ADDR"] = "10.0.0.1"
        blocked = view(second)
        self.assertEqual(blocked.status_code, 429)
        self.assertEqual(blocked.data["detail"], "Rate limit exceeded. Try again later.")
        self.assertEqual(blocked["Retry-After"], "50")

    def test_tracks_clients_separately(self):
        view = self._build_view(max_requests=1, per="minute")

        req_a = self.factory.get("/limited/")
        req_a.META["REMOTE_ADDR"] = "10.0.0.1"
        self.assertEqual(view(req_a).status_code, 200)

        req_b = self.factory.get("/limited/")
        req_b.META["REMOTE_ADDR"] = "10.0.0.2"
        self.assertEqual(view(req_b).status_code, 200)

    @patch("api.decorators.monotonic", side_effect=[0, 0, 61])
    def test_resets_limit_when_window_changes(self, _mock_time):
        view = self._build_view(max_requests=1, per="minute")

        first = self.factory.get("/limited/")
        first.META["REMOTE_ADDR"] = "10.0.0.1"
        self.assertEqual(view(first).status_code, 200)

        second = self.factory.get("/limited/")
        second.META["REMOTE_ADDR"] = "10.0.0.1"
        self.assertEqual(view(second).status_code, 429)

        third = self.factory.get("/limited/")
        third.META["REMOTE_ADDR"] = "10.0.0.1"
        allowed_again = view(third)
        self.assertEqual(allowed_again.status_code, 200)
        self.assertEqual(allowed_again["X-RateLimit-Remaining"], "0")

    @patch("api.decorators.monotonic", return_value=0)
    @patch("api.decorators.cache")
    def test_falls_back_when_cache_incr_key_missing(self, mock_cache, _mock_time):
        view = self._build_view(max_requests=2, per="minute")

        mock_cache.add.side_effect = [False, True]
        mock_cache.incr.side_effect = ValueError("key does not exist")

        req = self.factory.get("/limited/")
        req.META["REMOTE_ADDR"] = "10.10.10.10"
        response = view(req)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["X-RateLimit-Limit"], "2")
        self.assertEqual(response["X-RateLimit-Remaining"], "1")
        self.assertEqual(mock_cache.incr.call_count, 1)
        self.assertEqual(mock_cache.add.call_count, 2)

    def test_uses_first_forwarded_ip_when_present(self):
        view = self._build_view(max_requests=1, per="minute")

        forwarded = self.factory.get("/limited/")
        forwarded.META["HTTP_X_FORWARDED_FOR"] = "203.0.113.1, 10.0.0.2"
        forwarded.META["REMOTE_ADDR"] = "10.0.0.9"
        self.assertEqual(view(forwarded).status_code, 200)

        same_forwarded = self.factory.get("/limited/")
        same_forwarded.META["HTTP_X_FORWARDED_FOR"] = "203.0.113.1, 10.0.0.2"
        same_forwarded.META["REMOTE_ADDR"] = "10.0.0.7"
        blocked = view(same_forwarded)
        self.assertEqual(blocked.status_code, 429)

    @patch("api.decorators.monotonic", side_effect=[0, 0, 0])
    def test_supports_custom_key_func(self, _mock_time):
        @api_view(["GET"])
        @rate_limit(max_requests=1, per="minute", key_func=lambda request: request.headers.get("X-Client", "anon"))
        def by_client_header(request):
            return Response({"ok": True})

        first = self.factory.get("/limited/", HTTP_X_CLIENT="client-a")
        self.assertEqual(by_client_header(first).status_code, 200)

        second = self.factory.get("/limited/", HTTP_X_CLIENT="client-a")
        self.assertEqual(by_client_header(second).status_code, 429)

        other = self.factory.get("/limited/", HTTP_X_CLIENT="client-b")
        self.assertEqual(by_client_header(other).status_code, 200)

    @patch("api.decorators.monotonic", side_effect=[10, 10])
    def test_supports_custom_error_payload_status_and_code(self, _mock_time):
        @api_view(["GET"])
        @rate_limit(
            max_requests=1,
            per="minute",
            error_detail="Too many requests for this endpoint.",
            error_status=503,
            error_code="rate_limited",
        )
        def limited_custom_error(request):
            return Response({"ok": True})

        first = self.factory.get("/limited-custom/")
        first.META["REMOTE_ADDR"] = "10.0.0.1"
        self.assertEqual(limited_custom_error(first).status_code, 200)

        second = self.factory.get("/limited-custom/")
        second.META["REMOTE_ADDR"] = "10.0.0.1"
        blocked = limited_custom_error(second)
        self.assertEqual(blocked.status_code, 503)
        self.assertEqual(blocked.data["detail"], "Too many requests for this endpoint.")
        self.assertEqual(blocked.data["code"], "rate_limited")
        self.assertEqual(blocked["Retry-After"], "50")


class RateLimitDecoratorValidationTest(SimpleTestCase):
    def test_rejects_invalid_window(self):
        with self.assertRaises(ValueError):
            rate_limit(max_requests=1, per="hour")

    def test_rejects_non_positive_limit(self):
        with self.assertRaises(ValueError):
            rate_limit(max_requests=0, per="minute")

    def test_rejects_non_callable_key_func(self):
        with self.assertRaises(ValueError):
            rate_limit(max_requests=1, per="minute", key_func="not-a-callable")

    def test_rejects_non_positive_error_status(self):
        with self.assertRaises(ValueError):
            rate_limit(max_requests=1, per="minute", error_status=0)
