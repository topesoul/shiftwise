# Generated by Django 5.1.2 on 2024-11-21 04:05

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("shifts", "0016_alter_shift_end_date"),
    ]

    operations = [
        migrations.AddField(
            model_name="shift",
            name="shift_role",
            field=models.CharField(
                choices=[
                    ("Staff", "Staff"),
                    ("Manager", "Manager"),
                    ("Admin", "Admin"),
                    ("Care Worker", "Healthcare Worker"),
                    ("Kitchen Staff", "Kitchen"),
                    ("Front Office Staff", "Front Office"),
                    ("Receptionist", "Receptionist"),
                    ("Chef", "Chef"),
                    ("Waiter", "Waiter"),
                    ("Dishwasher", "Dishwasher"),
                    ("Laundry Staff", "Laundry"),
                    ("Housekeeping Staff", "Housekeeping"),
                    ("Other", "Other"),
                ],
                default="Staff",
                help_text="Select the role required for this shift.",
                max_length=100,
            ),
        ),
    ]
