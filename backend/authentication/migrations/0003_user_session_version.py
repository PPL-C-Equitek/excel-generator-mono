from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0002_user_email_verification_nonce"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="session_version",
            field=models.IntegerField(default=1),
        ),
    ]
