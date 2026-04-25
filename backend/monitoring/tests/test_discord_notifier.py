from types import SimpleNamespace
from urllib.error import URLError
from unittest.mock import patch

from django.test import SimpleTestCase

from monitoring.infrastructure.discord_notifier import (
    _post_to_discord_webhook,
    DiscordWebhookNotifier,
)


class _RequestCapture:
    def __init__(self):
        self.full_url = None
        self.data = None
        self.headers = None
        self.method = None
        self.timeout = None

    def __call__(self, request, timeout=None):
        self.full_url = getattr(request, "full_url", None)
        self.data = getattr(request, "data", None)
        self.headers = dict(getattr(request, "headers", {}))
        self.method = getattr(request, "method", None)
        self.timeout = timeout
        return self

    def __enter__(self):
        return SimpleNamespace(read=lambda: b"ok")

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False


class _WebhookCallRecorder:
    def __init__(self):
        self.calls = []

    def __call__(self, *, webhook_url, payload, timeout_seconds):
        self.calls.append(
            SimpleNamespace(
                webhook_url=webhook_url,
                payload=payload,
                timeout_seconds=timeout_seconds,
            )
        )


class DiscordWebhookNotifierTest(SimpleTestCase):
    def test_notify_does_nothing_when_webhook_url_empty(self):
        recorder = _WebhookCallRecorder()
        notifier = DiscordWebhookNotifier(
            webhook_url="   ",
            post_callable=recorder,
        )

        notifier.notify(event_name="monitoring.readiness", payload={"status": "down"})

        self.assertEqual(len(recorder.calls), 0)

    def test_notify_builds_payload_and_calls_sender(self):
        recorder = _WebhookCallRecorder()
        notifier = DiscordWebhookNotifier(
            webhook_url="https://discord.test/webhook",
            username=" ",
            timeout_seconds=2.0,
            post_callable=recorder,
        )

        notifier.notify(
            event_name="monitoring.readiness",
            payload={
                "status": "down",
                "http_status": 503,
                "timestamp": "2026-04-20T10:05:00",
                "checks": [{"name": "db", "status": "error"}],
            },
        )

        self.assertEqual(len(recorder.calls), 1)
        call = recorder.calls[0]
        self.assertEqual(call.webhook_url, "https://discord.test/webhook")
        self.assertEqual(call.timeout_seconds, 2.0)
        self.assertEqual(call.payload["username"], "MonitoringBot")
        self.assertEqual(call.payload["content"], "[Monitoring] monitoring.readiness")
        self.assertEqual(
            call.payload["embeds"][0]["fields"][0]["value"],
            "down",
        )

    def test_notify_swallows_http_errors(self):
        def failing_sender(*, webhook_url, payload, timeout_seconds):
            raise RuntimeError("network down")

        notifier = DiscordWebhookNotifier(
            webhook_url="https://discord.test/webhook",
            post_callable=failing_sender,
        )

        notifier.notify(event_name="monitoring.readiness", payload={"status": "down"})

    def test_notify_swallows_communication_errors(self):
        def failing_sender(*, webhook_url, payload, timeout_seconds):
            raise URLError("endpoint unavailable")

        notifier = DiscordWebhookNotifier(
            webhook_url="https://discord.test/webhook",
            post_callable=failing_sender,
        )

        notifier.notify(event_name="monitoring.readiness", payload={"status": "down"})

    def test_post_to_discord_webhook_sends_json_payload(self):
        request_capture = _RequestCapture()
        payload = {"content": "test"}
        with patch("monitoring.infrastructure.discord_notifier.urlopen", new=request_capture):
            _post_to_discord_webhook(
                webhook_url="https://discord.test/webhook",
                payload=payload,
                timeout_seconds=7.5,
            )

        self.assertEqual(request_capture.full_url, "https://discord.test/webhook")
        self.assertEqual(request_capture.method, "POST")
        self.assertEqual(request_capture.timeout, 7.5)
        self.assertEqual(request_capture.headers["Content-Type"], "application/json")
        self.assertEqual(request_capture.data, b'{"content":"test"}')
