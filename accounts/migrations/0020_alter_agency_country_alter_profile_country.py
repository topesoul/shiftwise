# Generated by Django 5.1.2 on 2024-11-21 02:38

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0019_alter_profile_options_alter_agency_address_line1_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="agency",
            name="country",
            field=models.CharField(blank=True, default="UK", max_length=100, null=True),
        ),
        migrations.AlterField(
            model_name="profile",
            name="country",
            field=models.CharField(blank=True, default="UK", max_length=100, null=True),
        ),
    ]
