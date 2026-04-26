import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class Session(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        "authentication.User",
        db_column="owner_id",
        on_delete=models.CASCADE,
        related_name="chat_sessions",
    )
    title = models.CharField(max_length=120, blank=True, default="")
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    last_message_at = models.DateTimeField(null=True, blank=True)
    last_output_at = models.DateTimeField(null=True, blank=True)
    history_summary = models.TextField(blank=True, default="")
    history_summary_watermark = models.IntegerField(default=0)

    class Meta:
        ordering = ("-last_message_at", "-updated_at", "-created_at", "-id")
        indexes = [
            models.Index(
                fields=("owner", "-last_message_at", "-updated_at", "-created_at"),
                name="session_owner_recency_idx",
            ),
        ]


class ChatMessage(models.Model):
    ROLE_USER = "user"
    ROLE_ASSISTANT = "assistant"
    ROLE_CHOICES = (
        (ROLE_USER, "User"),
        (ROLE_ASSISTANT, "Assistant"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(
        "chat_sessions.Session",
        on_delete=models.CASCADE,
        related_name="messages",
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    content = models.TextField()
    thinking_log = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        indexes = [
            models.Index(
                fields=("session", "created_at", "id"),
                name="chatmsg_sess_created_idx",
            ),
        ]


class GeneratedOutput(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(
        "chat_sessions.Session",
        on_delete=models.CASCADE,
        related_name="generated_outputs",
    )
    output_json = models.JSONField()
    export_output_json = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        indexes = [
            models.Index(
                fields=("session", "created_at", "id"),
                name="genout_sess_created_idx",
            ),
        ]

    def clean(self):
        super().clean()
        if not isinstance(self.output_json, dict):
            raise ValidationError({"output_json": "output_json must be an object."})
        if not isinstance(self.export_output_json, dict):
            raise ValidationError(
                {"export_output_json": "export_output_json must be an object."}
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)
