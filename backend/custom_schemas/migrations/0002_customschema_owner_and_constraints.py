from django.db import migrations, models


def delete_existing_custom_schemas(apps, schema_editor):
    CustomSchema = apps.get_model("custom_schemas", "CustomSchema")
    CustomSchema.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("custom_schemas", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(
            delete_existing_custom_schemas,
            migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name="customschema",
            name="name",
            field=models.CharField(max_length=120),
        ),
        migrations.AddField(
            model_name="customschema",
            name="owner_id",
            field=models.UUIDField(db_index=True),
        ),
        migrations.AddConstraint(
            model_name="customschema",
            constraint=models.UniqueConstraint(
                fields=("owner_id", "name"),
                name="unique_custom_schema_name_per_owner_id",
            ),
        ),
    ]
