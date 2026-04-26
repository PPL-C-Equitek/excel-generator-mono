from dataclasses import dataclass
from typing import Any

from monitoring.models import MonitoringAccount


@dataclass(frozen=True)
class MonitoringAccessDecision:
    allowed: bool
    reason: str

    def to_dict(self) -> dict[str, object]:
        return {
            "allowed": self.allowed,
            "reason": self.reason,
        }


class MonitoringAccessPolicy:
    def evaluate(self, user: Any) -> MonitoringAccessDecision:
        if not user or not getattr(user, "is_authenticated", False):
            return MonitoringAccessDecision(allowed=False, reason="unauthenticated")

        if getattr(user, "status", None) != "verified":
            return MonitoringAccessDecision(allowed=False, reason="unverified")

        try:
            account = user.monitoring_account
        except MonitoringAccount.DoesNotExist:
            return MonitoringAccessDecision(allowed=False, reason="no_account")

        if not account.is_active:
            return MonitoringAccessDecision(allowed=False, reason="inactive")

        return MonitoringAccessDecision(allowed=True, reason="ok")

