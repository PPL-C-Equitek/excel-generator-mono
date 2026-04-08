from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0001_initial"),
        ("custom_schemas", "0004_remove_customschema_version"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="customschema",
            name="unique_custom_schema_name_per_owner_id",
        ),
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.RemoveField(
                    model_name="customschema",
                    name="owner_id",
                ),
                migrations.AddField(
                    model_name="customschema",
                    name="owner",
                    field=models.ForeignKey(
                        db_column="owner_id",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="custom_schemas",
                        to="authentication.user",
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="customschema",
            constraint=models.UniqueConstraint(
                fields=("owner", "name"),
                name="unique_custom_schema_name_per_owner",
            ),
        ),
    ]
