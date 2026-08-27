"""
Finish the move to journal-scoped editions.

Everything ArchivedJournal recorded now lives on Issue (0015 copied the rows),
and every article's edition is a foreign key rather than two text fields, so the
legacy columns and the old model go. ``Journal.slug`` becomes unique now that
0015 has filled one in for every row.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('journalapp', '0015_seed_journals_and_issues'),
    ]

    operations = [
        migrations.AlterField(
            model_name='journal',
            name='slug',
            field=models.SlugField(
                max_length=80, unique=True,
                help_text="Used in the journal's web address, e.g. 'jjel'."),
        ),
        migrations.RemoveField(model_name='article', name='legacy_volume'),
        migrations.RemoveField(model_name='article', name='legacy_issue'),
        migrations.RemoveField(model_name='archivedjournal', name='department'),
        migrations.RemoveField(model_name='archivedjournal', name='uploaded_by'),
        migrations.DeleteModel(name='ArchivedJournal'),
    ]
