# Generated by Django 5.1.2 on 2024-11-11 21:54

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("subscriptions", "0012_plan_shift_management"),
    ]

    operations = [
        migrations.AlterField(
            model_name="plan",
            name="name",
            field=models.CharField(
                choices=[
                    ("Basic", "Basic"),
                    ("Pro", "Pro"),
                    ("Enterprise", "Enterprise"),
                ],
                max_length=100,
            ),
        ),
    ]
