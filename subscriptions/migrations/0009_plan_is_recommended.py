# Generated by Django 5.1.2 on 2024-11-06 20:41

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("subscriptions", "0008_remove_plan_is_recommended"),
    ]

    operations = [
        migrations.AddField(
            model_name="plan",
            name="is_recommended",
            field=models.BooleanField(default=False),
        ),
    ]
