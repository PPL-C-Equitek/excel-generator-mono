import uuid

from django.db import models

from .definition_service import (
    build_schema_prompt_fragment,
    validate_schema_definition,
)


class CustomSchema(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        "authentication.User",
        db_column="owner_id",
        on_delete=models.CASCADE,
        related_name="custom_schemas",
    )
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    definition = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("name", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("owner", "name"),
                name="unique_custom_schema_name_per_owner",
            )
        ]

    def __str__(self):
        return self.name

    @property
    def prompt_fragment(self):
        return build_schema_prompt_fragment(self.definition)

    def clean(self):
        super().clean()
        validate_schema_definition(self.definition)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)
