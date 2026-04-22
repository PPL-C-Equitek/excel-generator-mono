from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.http import HttpResponse
from django.test import SimpleTestCase
from rest_framework.test import APIRequestFactory

from monitoring.interfaces.http.middleware import MonitoringRequestMetricsMiddleware


class MonitoringRequestMetricsMiddlewareTest(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    @patch("monitoring.interfaces.http.middleware.get_monitoring_service")
    def test_middleware_records_metrics_for_success_response(self, mocked_get_service):
        monitoring_service = Mock()
        mocked_get_service.return_value = monitoring_service

        middleware = MonitoringRequestMetricsMiddleware(
            lambda request: HttpResponse(status=201)
        )
        request = self.factory.post("/auth/login/")
        request.resolver_match = SimpleNamespace(route="auth/login/")

        response = middleware(request)

        self.assertEqual(response.status_code, 201)
        monitoring_service.record_request.assert_called_once()
        called_kwargs = monitoring_service.record_request.call_args.kwargs
        self.assertEqual(called_kwargs["route"], "auth/login/")
        self.assertEqual(called_kwargs["method"], "POST")
        self.assertEqual(called_kwargs["status_code"], 201)
        self.assertGreaterEqual(called_kwargs["duration_ms"], 0.0)

    @patch("monitoring.interfaces.http.middleware.get_monitoring_service")
    def test_middleware_records_500_and_reraises_when_view_throws(self, mocked_get_service):
        monitoring_service = Mock()
        mocked_get_service.return_value = monitoring_service

        def _raise(_request):
            raise RuntimeError("unexpected")

        middleware = MonitoringRequestMetricsMiddleware(_raise)
        request = self.factory.get("/boom/")

        with self.assertRaises(RuntimeError):
            middleware(request)

        monitoring_service.record_request.assert_called_once()
        called_kwargs = monitoring_service.record_request.call_args.kwargs
        self.assertEqual(called_kwargs["status_code"], 500)
        self.assertEqual(called_kwargs["route"], "/boom/")

    @patch("monitoring.interfaces.http.middleware.logger")
    @patch("monitoring.interfaces.http.middleware.get_monitoring_service")
    def test_middleware_swallows_metrics_recording_errors(
        self,
        mocked_get_service,
        mocked_logger,
    ):
        monitoring_service = Mock()
        monitoring_service.record_request.side_effect = RuntimeError("metrics down")
        mocked_get_service.return_value = monitoring_service

        middleware = MonitoringRequestMetricsMiddleware(
            lambda request: HttpResponse(status=200)
        )
        request = self.factory.get("/health/")

        response = middleware(request)

        self.assertEqual(response.status_code, 200)
        mocked_logger.exception.assert_called_once_with("Failed to record request metrics.")

    def test_resolve_route_falls_back_to_path_when_route_is_missing(self):
        request = self.factory.get("/fallback/")
        request.resolver_match = SimpleNamespace(route=None)

        route = MonitoringRequestMetricsMiddleware._resolve_route(request)

        self.assertEqual(route, "/fallback/")

