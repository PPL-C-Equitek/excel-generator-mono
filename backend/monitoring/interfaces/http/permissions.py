from rest_framework.permissions import BasePermission

from monitoring.models import MonitoringAccount


class IsMonitoringAccount(BasePermission):
    message = "Monitoring account access is required."

    def has_permission(self, request, view) -> bool:
        user = request.user
        if not user or not user.is_authenticated:
            return False

        if getattr(user, "status", None) != "verified":
            return False

        try:
            account = user.monitoring_account
        except MonitoringAccount.DoesNotExist:
            return False

        return bool(account.has_access)

