from django.core.cache import cache
from django.test import SimpleTestCase
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory
from unittest.mock import patch

from api.decorators import (
    _build_cache_key,
    _build_rate_limited_response,
    _default_key_func,
    _execute_rate_limited_request,
    _increment_request_count,
    _set_rate_limit_headers,
    _validate_rate_limit_config,
    rate_limit,
)


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


class RateLimitHelperFunctionTest(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_default_key_func_returns_client_ip(self):
        request = self.factory.get("/limited/")
        request.META["REMOTE_ADDR"] = "192.168.1.1"
        self.assertEqual(_default_key_func(request), "192.168.1.1")

    def test_validate_rate_limit_config_returns_window_and_default_identity(self):
        window, identity_func = _validate_rate_limit_config(
            max_requests=2,
            per="minute",
            key_func=None,
            error_status=429,
        )
        self.assertEqual(window, 60)
        request = self.factory.get("/limited/")
        request.META["REMOTE_ADDR"] = "127.0.0.1"
        self.assertEqual(identity_func(request), "127.0.0.1")

    def test_build_cache_key_contains_method_path_identity_and_bucket(self):
        @api_view(["GET"])
        def sample_view(request):
            return Response({"ok": True})

        request = self.factory.get("/api/upload/")
        key = _build_cache_key(sample_view, request, "client-x", 12)
        self.assertIn(f"api.tests.test_decorators.{sample_view.__name__}", key)
        self.assertIn("GET:/api/upload/:client-x:12", key)

    @patch("api.decorators.cache")
    def test_increment_request_count_returns_one_on_first_request(self, mock_cache):
        mock_cache.add.return_value = True
        result = _increment_request_count("k1", 60)
        self.assertEqual(result, 1)
        mock_cache.incr.assert_not_called()

    @patch("api.decorators.cache")
    def test_increment_request_count_uses_incr_when_key_exists(self, mock_cache):
        mock_cache.add.return_value = False
        mock_cache.incr.return_value = 3
        result = _increment_request_count("k2", 60)
        self.assertEqual(result, 3)
        mock_cache.incr.assert_called_once_with("k2")

    @patch("api.decorators.cache")
    def test_increment_request_count_falls_back_when_incr_raises(self, mock_cache):
        mock_cache.add.side_effect = [False, True]
        mock_cache.incr.side_effect = ValueError("missing")
        result = _increment_request_count("k3", 60)
        self.assertEqual(result, 1)
        self.assertEqual(mock_cache.add.call_count, 2)

    def test_set_rate_limit_headers_sets_limit_and_remaining(self):
        response = Response({"ok": True}, status=200)
        updated = _set_rate_limit_headers(response, max_requests=10, remaining=7)
        self.assertEqual(updated["X-RateLimit-Limit"], "10")
        self.assertEqual(updated["X-RateLimit-Remaining"], "7")

    def test_build_rate_limited_response_contains_retry_headers_and_code(self):
        response = _build_rate_limited_response(
            current_time=10,
            bucket=0,
            window=60,
            max_requests=5,
            error_detail="Too many requests.",
            error_status=429,
            error_code="rate_limit_exceeded",
        )
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.data["detail"], "Too many requests.")
        self.assertEqual(response.data["code"], "rate_limit_exceeded")
        self.assertEqual(response["Retry-After"], "50")
        self.assertEqual(response["X-RateLimit-Limit"], "5")
        self.assertEqual(response["X-RateLimit-Remaining"], "0")

    @patch("api.decorators._increment_request_count", return_value=1)
    @patch("api.decorators.monotonic", return_value=5)
    def test_execute_rate_limited_request_allows_and_sets_headers(self, _mock_time, _mock_count):
        @api_view(["GET"])
        def sample_view(request):
            return Response({"ok": True})

        request = self.factory.get("/sample/")
        response = _execute_rate_limited_request(
            request=request,
            view_func=sample_view,
            args=(),
            kwargs={},
            max_requests=2,
            window=60,
            identity_func=lambda req: "identity-a",
            error_detail="blocked",
            error_status=429,
            error_code=None,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["X-RateLimit-Limit"], "2")
        self.assertEqual(response["X-RateLimit-Remaining"], "1")

    @patch("api.decorators._increment_request_count", return_value=3)
    @patch("api.decorators.monotonic", return_value=10)
    def test_execute_rate_limited_request_blocks_when_limit_exceeded(self, _mock_time, _mock_count):
        @api_view(["GET"])
        def sample_view(request):
            return Response({"ok": True})

        request = self.factory.get("/sample/")
        response = _execute_rate_limited_request(
            request=request,
            view_func=sample_view,
            args=(),
            kwargs={},
            max_requests=2,
            window=60,
            identity_func=lambda req: "identity-a",
            error_detail="blocked",
            error_status=429,
            error_code=None,
        )

        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.data["detail"], "blocked")
        self.assertEqual(response["Retry-After"], "50")
