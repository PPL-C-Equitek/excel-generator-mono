from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("custom_schemas", "0003_customschema_uuid_primary_key"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="customschema",
            name="version",
        ),
    ]
