import uuid

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="email_verification_nonce",
            field=models.UUIDField(default=uuid.uuid4, editable=False),
        ),
    ]
