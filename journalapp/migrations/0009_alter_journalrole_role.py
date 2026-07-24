# Collapse the three-role model to two: the 'admin' role merges into
# 'chief_editor' (one lead person per journal does both).

from django.db import migrations, models


def merge_admin_into_chief_editor(apps, schema_editor):
    """Convert any Journal Admin rows to Chief Editor.

    If a user already holds Chief Editor on the same journal, the admin row is
    dropped instead of converted, so the unique (user, journal, role) constraint
    is never violated.
    """
    JournalRole = apps.get_model('journalapp', 'JournalRole')
    for role in JournalRole.objects.filter(role='admin'):
        clash = JournalRole.objects.filter(
            user_id=role.user_id, journal_id=role.journal_id, role='chief_editor'
        ).exists()
        if clash:
            role.delete()
        else:
            role.role = 'chief_editor'
            role.save(update_fields=['role'])


def noop_reverse(apps, schema_editor):
    """Irreversible in data terms — merged rows can't be told apart to split back."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('journalapp', '0008_backfill_journal_roles'),
    ]

    operations = [
        migrations.RunPython(merge_admin_into_chief_editor, noop_reverse),
        migrations.AlterField(
            model_name='journalrole',
            name='role',
            field=models.CharField(choices=[('chief_editor', 'Chief Editor'), ('editor', 'Editor')], max_length=20),
        ),
    ]
