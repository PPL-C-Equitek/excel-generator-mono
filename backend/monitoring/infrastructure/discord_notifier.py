from __future__ import annotations

import json
import logging
from itertools import islice
from typing import Callable, Mapping, TypeAlias
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

DiscordPayload: TypeAlias = dict[str, object]
DiscordPostCallable: TypeAlias = Callable[..., None]


def _post_to_discord_webhook(
    *,
    webhook_url: str,
    payload: DiscordPayload,
    timeout_seconds: float,
) -> None:
    request = Request(
        webhook_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=timeout_seconds) as response:
        # Consume response body so socket can be reused by urllib internals.
        response.read()


class DiscordWebhookNotifier:
    def __init__(
        self,
        *,
        webhook_url: str,
        username: str = "MonitoringBot",
        timeout_seconds: float = 3.0,
        post_callable: DiscordPostCallable | None = None,
    ) -> None:
        self._webhook_url = str(webhook_url).strip()
        self._username = str(username).strip() or "MonitoringBot"
        self._timeout_seconds = float(timeout_seconds)
        self._post_callable = post_callable or _post_to_discord_webhook

    def notify(self, *, event_name: str, payload: Mapping[str, object]) -> None:
        if not self._webhook_url:
            return

        message = self._build_message(event_name=event_name, payload=payload)
        try:
            self._post_callable(
                webhook_url=self._webhook_url,
                payload=message,
                timeout_seconds=self._timeout_seconds,
            )
        except (OSError, ValueError):
            logger.exception("Failed to notify discord webhook.")
        except Exception:
            logger.exception(
                "Unexpected error while notifying discord webhook.",
            )

    def _build_message(self, *, event_name: str, payload: Mapping[str, object]) -> DiscordPayload:
        checks_data = payload.get("checks", ())
        checks_preview = (
            list(islice(checks_data, 3)) if isinstance(checks_data, (list, tuple)) else []
        )
        return {
            "username": self._username,
            "content": f"[Monitoring] {event_name}",
            "embeds": [
                {
                    "title": "Monitoring Alert",
                    "color": 16711680,
                    "fields": [
                        {
                            "name": "Status",
                            "value": str(payload.get("status", "unknown")),
                            "inline": True,
                        },
                        {
                            "name": "HTTP Status",
                            "value": str(payload.get("http_status", "unknown")),
                            "inline": True,
                        },
                        {
                            "name": "Checks sample",
                            "value": json.dumps(checks_preview),
                            "inline": False,
                        },
                    ],
                    "timestamp": str(payload.get("timestamp", "")),
                }
            ],
        }
