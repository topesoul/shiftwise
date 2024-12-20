# Generated by Django 5.1.2 on 2024-11-05 10:35

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("shifts", "0007_shiftassignment_signature"),
    ]

    operations = [
        migrations.AddField(
            model_name="shiftassignment",
            name="attendance_status",
            field=models.CharField(
                blank=True,
                choices=[
                    ("attended", "Attended"),
                    ("late", "Late"),
                    ("no_show", "No Show"),
                ],
                help_text="Select attendance status after the shift.",
                max_length=20,
                null=True,
            ),
        ),
    ]
