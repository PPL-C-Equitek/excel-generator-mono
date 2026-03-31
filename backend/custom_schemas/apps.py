from django.apps import AppConfig


class CustomSchemasConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "custom_schemas"
