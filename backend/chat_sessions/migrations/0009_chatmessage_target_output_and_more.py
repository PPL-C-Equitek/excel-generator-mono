from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("chat_sessions", "0008_generatedoutput_reasoning"),
    ]

    operations = [
        migrations.AddField(
            model_name="chatmessage",
            name="target_output",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="targeted_by_messages",
                to="chat_sessions.generatedoutput",
            ),
        ),
        migrations.AddField(
            model_name="generatedoutput",
            name="parent_output",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="refined_outputs",
                to="chat_sessions.generatedoutput",
            ),
        ),
        migrations.AddField(
            model_name="generatedoutput",
            name="source_message",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="generated_outputs",
                to="chat_sessions.chatmessage",
            ),
        ),
    ]
