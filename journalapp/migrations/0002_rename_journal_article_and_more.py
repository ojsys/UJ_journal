# Generated by Django 5.1.7 on 2025-03-27 18:28

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('journalapp', '0001_initial'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='Journal',
            new_name='Article',
        ),
        migrations.RenameModel(
            old_name='JournalCategory',
            new_name='ArticleCategory',
        ),
        migrations.RenameField(
            model_name='comment',
            old_name='journal',
            new_name='article',
        ),
        migrations.RenameField(
            model_name='review',
            old_name='journal',
            new_name='article',
        ),
        migrations.AddField(
            model_name='department',
            name='cover_image',
            field=models.ImageField(blank=True, null=True, upload_to='department_covers'),
        ),
        migrations.AddField(
            model_name='department',
            name='journal_description',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='department',
            name='journal_title',
            field=models.CharField(blank=True, max_length=200),
        ),
    ]
