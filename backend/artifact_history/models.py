import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class ArtifactHistory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        "authentication.User",
        db_column="owner_id",
        on_delete=models.CASCADE,
        related_name="artifact_histories",
    )
    original_name = models.CharField(max_length=255)
    custom_name = models.CharField(max_length=255, blank=True, default="")
    output_json = models.JSONField()
    status_processing = models.CharField(max_length=50)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ("-created_at", "-id")

    def clean(self):
        super().clean()
        if self.custom_name is None:
            self.custom_name = ""
        if not isinstance(self.output_json, dict):
            raise ValidationError({"output_json": "output_json must be an object."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)
