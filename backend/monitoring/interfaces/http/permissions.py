from rest_framework.permissions import BasePermission

from monitoring.application.access_policy import MonitoringAccessPolicy


class IsMonitoringAccount(BasePermission):
    message = "Monitoring account access is required."
    _messages_by_reason = {
        "unauthenticated": "Authentication credentials were not provided.",
        "unverified": "Verified account is required.",
        "no_account": "Monitoring account access is required.",
        "inactive": "Monitoring account is inactive.",
    }

    def has_permission(self, request, view) -> bool:
        decision = MonitoringAccessPolicy().evaluate(getattr(request, "user", None))
        self.message = self._messages_by_reason.get(
            decision.reason,
            "Monitoring account access is required.",
        )
        return decision.allowed
