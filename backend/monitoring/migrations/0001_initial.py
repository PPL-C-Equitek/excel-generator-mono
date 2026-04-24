from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("authentication", "0002_user_email_verification_nonce"),
    ]

    operations = [
        migrations.CreateModel(
            name="MonitoringAccount",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="monitoring_account",
                        to="authentication.user",
                    ),
                ),
            ],
            options={
                "db_table": "monitoring_accounts",
            },
        ),
    ]

