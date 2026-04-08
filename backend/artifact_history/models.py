import uuid

from django.core.exceptions import ValidationError
from django.db import models


class ArtifactHistory(models.Model):
    FILE_TYPE_CSV = "csv"
    FILE_TYPE_ZIP = "zip"
    FILE_TYPE_XLSX = "xlsx"
    FILE_TYPE_CHOICES = (
        (FILE_TYPE_CSV, "CSV"),
        (FILE_TYPE_ZIP, "ZIP"),
        (FILE_TYPE_XLSX, "XLSX"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        "authentication.User",
        db_column="owner_id",
        on_delete=models.CASCADE,
        related_name="artifact_histories",
    )
    file_id = models.CharField(max_length=255, unique=True)
    original_name = models.CharField(max_length=255)
    custom_name = models.CharField(max_length=255, blank=True, null=True)
    file_name = models.CharField(max_length=255)
    file_type = models.CharField(max_length=10, choices=FILE_TYPE_CHOICES)
    status_processing = models.CharField(max_length=50)
    size_bytes = models.PositiveBigIntegerField()
    created_at = models.DateTimeField()

    class Meta:
        ordering = ("-created_at", "-id")

    def clean(self):
        super().clean()
        if self.file_type not in {
            self.FILE_TYPE_CSV,
            self.FILE_TYPE_ZIP,
            self.FILE_TYPE_XLSX,
        }:
            raise ValidationError({"file_type": "Unsupported artifact file type."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)
