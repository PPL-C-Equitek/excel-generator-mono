from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings

from monitoring.checks import (
    BaseHealthCheck,
    DatabaseHealthCheck,
    OpenAIConfigHealthCheck,
    StorageHealthCheck,
)


class _SuccessfulCheck(BaseHealthCheck):
    name = "dummy"
    is_critical = True

    def perform_check(self) -> None:
        return None


class _FailingCheck(BaseHealthCheck):
    name = "dummy_fail"
    is_critical = False

    def perform_check(self) -> None:
        raise RuntimeError("boom")


class _SilentFailingCheck(BaseHealthCheck):
    name = "silent_fail"
    is_critical = True

    class SilentError(Exception):
        pass

    def perform_check(self) -> None:
        raise self.SilentError()


class BaseHealthCheckTest(SimpleTestCase):
    def test_base_perform_check_raises_not_implemented(self):
        with self.assertRaises(NotImplementedError):
            BaseHealthCheck.perform_check(object())

    def test_run_returns_ok_result(self):
        result = _SuccessfulCheck().run()

        self.assertEqual(result.name, "dummy")
        self.assertEqual(result.status, "ok")
        self.assertEqual(result.message, "")
        self.assertTrue(result.is_critical)
        self.assertGreaterEqual(result.latency_ms, 0)

    def test_run_returns_error_result(self):
        result = _FailingCheck().run()

        self.assertEqual(result.name, "dummy_fail")
        self.assertEqual(result.status, "error")
        self.assertEqual(result.message, "boom")
        self.assertFalse(result.is_critical)

    def test_run_uses_exception_class_name_when_message_empty(self):
        result = _SilentFailingCheck().run()

        self.assertEqual(result.name, "silent_fail")
        self.assertEqual(result.status, "error")
        self.assertEqual(result.message, "SilentError")


class DatabaseHealthCheckTest(SimpleTestCase):
    def test_perform_check_executes_select_one(self):
        mock_cursor = MagicMock()
        mock_connection = MagicMock()
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        with patch("monitoring.infrastructure.health_checks.connections", {"default": mock_connection}):
            DatabaseHealthCheck(alias="default").perform_check()

        mock_cursor.execute.assert_called_once_with("SELECT 1")
        mock_cursor.fetchone.assert_called_once()


class StorageHealthCheckTest(SimpleTestCase):
    def test_perform_check_succeeds_for_writable_directory(self):
        with TemporaryDirectory() as directory:
            check = StorageHealthCheck(path=directory)
            check.perform_check()

    def test_perform_check_raises_when_directory_missing(self):
        check = StorageHealthCheck(path="missing-directory")

        with self.assertRaises(FileNotFoundError):
            check.perform_check()

    def test_perform_check_raises_when_directory_not_writable(self):
        with TemporaryDirectory() as directory:
            check = StorageHealthCheck(path=directory)
            with patch("monitoring.infrastructure.health_checks.os.access", return_value=False):
                with self.assertRaises(PermissionError):
                    check.perform_check()


class OpenAIConfigHealthCheckTest(SimpleTestCase):
    @override_settings(OPENAI_API_KEY="")
    def test_perform_check_raises_when_api_key_is_missing(self):
        with self.assertRaises(RuntimeError):
            OpenAIConfigHealthCheck().perform_check()

    @override_settings(OPENAI_API_KEY="sk-test")
    def test_perform_check_succeeds_when_api_key_exists(self):
        OpenAIConfigHealthCheck().perform_check()
