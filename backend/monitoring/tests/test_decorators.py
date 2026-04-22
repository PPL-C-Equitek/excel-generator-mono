from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase
from rest_framework.test import APIRequestFactory

from monitoring.interfaces.http.decorators import _resolve_auth_outcome, track_auth_metric


class ResolveAuthOutcomeTest(SimpleTestCase):
    def test_resolve_auth_outcome_returns_success(self):
        self.assertEqual(_resolve_auth_outcome(200), "success")

    def test_resolve_auth_outcome_returns_client_error(self):
        self.assertEqual(_resolve_auth_outcome(409), "client_error")

    def test_resolve_auth_outcome_returns_server_error(self):
        self.assertEqual(_resolve_auth_outcome(500), "server_error")

    def test_resolve_auth_outcome_returns_unknown_for_non_integer_status(self):
        self.assertEqual(_resolve_auth_outcome(None), "unknown")


class TrackAuthMetricDecoratorTest(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    @patch("monitoring.interfaces.http.decorators.get_monitoring_service")
    def test_track_auth_metric_records_success_outcome(self, mocked_get_service):
        monitoring_service = Mock()
        mocked_get_service.return_value = monitoring_service

        class _View:
            @track_auth_metric("login")
            def post(self, request):
                return SimpleNamespace(status_code=200)

        request = self.factory.post("/auth/login/")
        _View().post(request)

        monitoring_service.record_event.assert_called_once_with(
            event_name="login",
            outcome="success",
            endpoint="/auth/login/",
        )

    @patch("monitoring.interfaces.http.decorators.get_monitoring_service")
    def test_track_auth_metric_records_unknown_outcome_when_status_is_missing(self, mocked_get_service):
        monitoring_service = Mock()
        mocked_get_service.return_value = monitoring_service

        @track_auth_metric("register")
        def wrapped_view(*, request):
            return object()

        request = self.factory.post("/auth/register/")
        wrapped_view(request=request)

        monitoring_service.record_event.assert_called_once_with(
            event_name="register",
            outcome="unknown",
            endpoint="/auth/register/",
        )

    @patch("monitoring.interfaces.http.decorators.get_monitoring_service")
    def test_track_auth_metric_records_exception_outcome_and_reraises(self, mocked_get_service):
        monitoring_service = Mock()
        mocked_get_service.return_value = monitoring_service

        class _View:
            @track_auth_metric("login")
            def post(self, request):
                raise RuntimeError("boom")

        request = self.factory.post("/auth/login/")
        with self.assertRaises(RuntimeError):
            _View().post(request)

        monitoring_service.record_event.assert_called_once_with(
            event_name="login",
            outcome="exception",
            endpoint="/auth/login/",
        )

    @patch("monitoring.interfaces.http.decorators.logger")
    @patch("monitoring.interfaces.http.decorators.get_monitoring_service")
    def test_track_auth_metric_swallows_monitoring_errors(
        self,
        mocked_get_service,
        mocked_logger,
    ):
        monitoring_service = Mock()
        monitoring_service.record_event.side_effect = RuntimeError("metrics down")
        mocked_get_service.return_value = monitoring_service

        class _View:
            @track_auth_metric("login")
            def post(self, request):
                return SimpleNamespace(status_code=200)

        request = self.factory.post("/auth/login/")
        response = _View().post(request)

        self.assertEqual(response.status_code, 200)
        mocked_logger.exception.assert_called_once_with("Failed to record auth metrics.")
