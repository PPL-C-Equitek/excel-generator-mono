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
    session_id = models.UUIDField(null=True, blank=True, db_index=True)
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


class HistoryExportArtifact(models.Model):
    REQUESTED_FORMAT_CSV = "csv"
    REQUESTED_FORMAT_XLSX = "xlsx"
    REQUESTED_FORMAT_CHOICES = (
        (REQUESTED_FORMAT_CSV, "CSV"),
        (REQUESTED_FORMAT_XLSX, "XLSX"),
    )

    ARTIFACT_TYPE_CSV = "csv"
    ARTIFACT_TYPE_ZIP = "zip"
    ARTIFACT_TYPE_XLSX = "xlsx"
    ARTIFACT_TYPE_CHOICES = (
        (ARTIFACT_TYPE_CSV, "CSV"),
        (ARTIFACT_TYPE_ZIP, "ZIP"),
        (ARTIFACT_TYPE_XLSX, "XLSX"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    history = models.ForeignKey(
        "artifact_history.ArtifactHistory",
        on_delete=models.CASCADE,
        related_name="export_artifacts",
    )
    owner = models.ForeignKey(
        "authentication.User",
        db_column="owner_id",
        on_delete=models.CASCADE,
        related_name="history_export_artifacts",
    )
    requested_format = models.CharField(max_length=10, choices=REQUESTED_FORMAT_CHOICES)
    artifact_type = models.CharField(max_length=10, choices=ARTIFACT_TYPE_CHOICES)
    file_id = models.CharField(max_length=255)
    file_name = models.CharField(max_length=255)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ("-created_at", "-id")
        constraints = [
            models.UniqueConstraint(
                fields=("history", "owner", "requested_format"),
                name="unique_history_export_artifact_per_format",
            )
        ]

    def clean(self):
        super().clean()
        if self.history_id and self.owner_id and self.history.owner_id != self.owner_id:
            raise ValidationError(
                {"owner": "owner must match the owner of the related history record."}
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)
