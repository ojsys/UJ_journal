# Generated by Django 5.1.7 on 2025-03-30 23:16

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('journalapp', '0006_archivedjournal'),
    ]

    operations = [
        migrations.AddField(
            model_name='archivedjournal',
            name='featured',
            field=models.BooleanField(default=False, help_text='Feature this archive on the home page'),
        ),
    ]
