from django.db import models

from authentication.models import User


class MonitoringAccountManager(models.Manager):
    def provision_for_user(
        self,
        *,
        user: User | None,
        is_active: bool = True,
    ) -> tuple["MonitoringAccount", bool]:
        if user is None:
            raise ValueError("user is required")

        account, created = self.get_or_create(
            user=user,
            defaults={"is_active": is_active},
        )
        if not created and account.is_active != is_active:
            account.is_active = is_active
            account.save(update_fields=["is_active", "updated_at"])
        return account, created


class MonitoringAccount(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="monitoring_account",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = MonitoringAccountManager()

    class Meta:
        db_table = "monitoring_accounts"

    def __str__(self) -> str:
        status = "active" if self.is_active else "inactive"
        return f"{self.user.email} ({status})"

    @property
    def has_access(self) -> bool:
        return bool(self.is_active and self.user.status == "verified")

