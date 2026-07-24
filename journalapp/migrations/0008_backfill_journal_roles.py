"""
Grant every existing staff user Chief Editor on every journal.

Editorial views are moving from the site-wide ``is_staff`` check to per-journal
roles. Site staff keep unrestricted access through
``journalapp.permissions.is_site_admin``, so this backfill is not what keeps
them working — it is here so the team screens show the current editorial team
instead of appearing empty, and so access survives a later decision to drop
someone's ``is_staff`` flag.

Superusers are skipped: they are unrestricted by definition, and listing them on
every journal's team page is noise.
"""
from django.db import migrations


def grant_chief_editor_to_staff(apps, schema_editor):
    JournalRole = apps.get_model('journalapp', 'JournalRole')
    Journal = apps.get_model('journalapp', 'Journal')
    User = apps.get_model('journalapp', 'CustomUser')

    journals = list(Journal.objects.all())
    if not journals:
        return

    staff = User.objects.filter(is_staff=True, is_superuser=False, is_active=True)

    JournalRole.objects.bulk_create(
        [
            JournalRole(user=user, journal=journal, role='chief_editor')
            for user in staff
            for journal in journals
        ],
        ignore_conflicts=True,
    )


def remove_backfilled_roles(apps, schema_editor):
    """Reverse: drop chief_editor rows that have no granter.

    ``granted_by`` is null exactly for rows this migration created — roles
    granted through the UI always record who granted them — so this leaves
    hand-assigned roles alone.
    """
    JournalRole = apps.get_model('journalapp', 'JournalRole')
    JournalRole.objects.filter(role='chief_editor', granted_by__isnull=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('journalapp', '0007_journalrole'),
    ]

    operations = [
        migrations.RunPython(grant_chief_editor_to_staff, remove_backfilled_roles),
    ]
