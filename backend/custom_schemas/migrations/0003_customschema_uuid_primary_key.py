import uuid

from django.db import migrations, models


def delete_existing_custom_schemas(apps, schema_editor):
    CustomSchema = apps.get_model("custom_schemas", "CustomSchema")
    CustomSchema.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("custom_schemas", "0002_customschema_owner_and_constraints"),
    ]

    operations = [
        migrations.RunPython(
            delete_existing_custom_schemas,
            migrations.RunPython.noop,
        ),
        migrations.RemoveField(
            model_name="customschema",
            name="id",
        ),
        migrations.AddField(
            model_name="customschema",
            name="id",
            field=models.UUIDField(
                default=uuid.uuid4,
                editable=False,
                primary_key=True,
                serialize=False,
            ),
        ),
    ]
