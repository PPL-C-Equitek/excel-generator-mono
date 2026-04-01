import uuid

from django.core.exceptions import ValidationError
from django.db import models

from .services import build_schema_prompt_fragment, validate_schema_definition


class CustomSchema(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner_id = models.UUIDField(db_index=True)
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    version = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)
    definition = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("name", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("owner_id", "name"),
                name="unique_custom_schema_name_per_owner_id",
            )
        ]

    def __str__(self):
        return f"{self.name} (v{self.version})"

    @property
    def prompt_fragment(self):
        return build_schema_prompt_fragment(self.definition)

    def clean(self):
        super().clean()

        if self.version < 1:
            raise ValidationError({"version": ["Version must be at least 1."]})

        validate_schema_definition(self.definition)

    def save(self, *args, **kwargs):
        if self.pk:
            previous = type(self).objects.filter(pk=self.pk).values(
                "definition",
                "version",
            ).first()
            if previous and previous["definition"] != self.definition:
                self.version = previous["version"] + 1

        self.full_clean()
        return super().save(*args, **kwargs)
