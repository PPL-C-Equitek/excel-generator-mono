import uuid

from django.db import models

from .services import build_schema_prompt_fragment, validate_schema_definition


class CustomSchema(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner_id = models.UUIDField(db_index=True)
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
                fields=("owner_id", "name"),
                name="unique_custom_schema_name_per_owner_id",
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
