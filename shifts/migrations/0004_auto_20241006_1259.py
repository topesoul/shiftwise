# Generated by Django 3.2.25 on 2024-10-06 12:59

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('shifts', '0003_populate_shift_fields'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='shift',
            name='address_line2',
        ),
        migrations.RemoveField(
            model_name='shift',
            name='country',
        ),
        migrations.RemoveField(
            model_name='shift',
            name='county',
        ),
        migrations.AddField(
            model_name='shift',
            name='capacity',
            field=models.PositiveIntegerField(default=1),
        ),
        migrations.AlterField(
            model_name='shift',
            name='latitude',
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='shift',
            name='longitude',
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.CreateModel(
            name='ShiftAssignment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('assigned_at', models.DateTimeField(auto_now_add=True)),
                ('shift', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='shifts.shift')),
                ('worker', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'unique_together': {('worker', 'shift')},
            },
        ),
    ]
