# Generated by Django 3.2.25 on 2024-10-06 18:37

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('shifts', '0006_auto_20241006_1815'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='shift',
            options={'ordering': ['shift_date', 'start_time']},
        ),
        migrations.AlterModelOptions(
            name='shiftassignment',
            options={'ordering': ['-assigned_at']},
        ),
        migrations.AddField(
            model_name='agency',
            name='agency_code',
            field=models.CharField(blank=True, max_length=20, unique=True),
        ),
    ]
