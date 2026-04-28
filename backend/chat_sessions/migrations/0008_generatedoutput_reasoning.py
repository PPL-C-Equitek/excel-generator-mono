from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("chat_sessions", "0007_generatedoutput_thinking_log"),
    ]

    operations = [
        migrations.AddField(
            model_name="generatedoutput",
            name="reasoning",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
