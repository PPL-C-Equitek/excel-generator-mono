from django.core.cache import cache
from django.test import SimpleTestCase
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory

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

    def test_blocks_request_after_limit(self):
        view = self._build_view(max_requests=1, per="minute")

        first = self.factory.get("/limited/")
        first.META["REMOTE_ADDR"] = "10.0.0.1"
        self.assertEqual(view(first).status_code, 200)

        second = self.factory.get("/limited/")
        second.META["REMOTE_ADDR"] = "10.0.0.1"
        blocked = view(second)
        self.assertEqual(blocked.status_code, 429)
        self.assertEqual(blocked.data["detail"], "Rate limit exceeded. Try again later.")
        self.assertEqual(blocked["Retry-After"], "60")

    def test_tracks_clients_separately(self):
        view = self._build_view(max_requests=1, per="minute")

        req_a = self.factory.get("/limited/")
        req_a.META["REMOTE_ADDR"] = "10.0.0.1"
        self.assertEqual(view(req_a).status_code, 200)

        req_b = self.factory.get("/limited/")
        req_b.META["REMOTE_ADDR"] = "10.0.0.2"
        self.assertEqual(view(req_b).status_code, 200)
