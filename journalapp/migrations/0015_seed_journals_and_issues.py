"""
Populate the three journals and turn legacy edition data into Issue rows.

The portal shipped with two placeholder journals named after departments. The
client actually runs three, two of which share the Department of English — which
is exactly why journals had to stop being addressed by department:

    Journal of English        -> Jos Journal of the English Language (JJEL)
    Journal of General Studies -> Humanity Journal
    (new)                      -> Jos Journal of Written and Oral Literature (JOJWOL)

The first is renamed rather than replaced because every existing article,
submission and category already points at it.

Also converts each distinct (journal, volume, issue) written on an article into
an Issue, and copies any ArchivedJournal rows across — those were keyed on
department, so an archive belonging to a department with several journals is
attached to that department's first journal and flagged in its description for
an editor to reassign.
"""
from django.db import migrations
from django.utils.text import slugify


# name -> (slug, abbreviation, order). Matched case-insensitively against the
# existing rows; anything unmatched is created.
JOURNALS = [
    {
        'match': 'journal of english',
        'name': 'Jos Journal of the English Language',
        'slug': 'jjel',
        'abbreviation': 'JJEL',
        'tagline': 'A peer-reviewed journal of English language studies.',
        'order': 1,
    },
    {
        'match': None,
        'name': 'Jos Journal of Written and Oral Literature',
        'slug': 'jojwol',
        'abbreviation': 'JOJWOL',
        'tagline': 'A peer-reviewed journal of written and oral literature.',
        'order': 2,
    },
    {
        'match': 'journal of general studies',
        'name': 'Humanity Journal',
        'slug': 'humanity',
        'abbreviation': 'Humanity',
        'tagline': 'A peer-reviewed journal of the humanities.',
        'order': 3,
    },
]


def seed_journals(apps, schema_editor):
    Journal = apps.get_model('journalapp', 'Journal')
    Department = apps.get_model('journalapp', 'Department')

    english = Department.objects.filter(name__icontains='english').first()

    for spec in JOURNALS:
        journal = None
        if spec['match']:
            journal = Journal.objects.filter(name__iexact=spec['match']).first()
        if journal is None:
            journal = Journal.objects.filter(slug=spec['slug']).first()
        if journal is None:
            journal = Journal.objects.filter(name__iexact=spec['name']).first()

        if journal is None:
            # JOJWOL has no placeholder to rename — create it under the same
            # department as JJEL, since both are English department journals.
            journal = Journal.objects.create(
                name=spec['name'], slug=spec['slug'], department=english,
            )

        journal.name = spec['name']
        journal.slug = spec['slug']
        journal.abbreviation = spec['abbreviation']
        journal.order = spec['order']
        journal.is_active = True
        if not journal.tagline:
            journal.tagline = spec['tagline']
        journal.save()

    # Any other journal already in the database keeps working: give it a slug
    # derived from its name so the unique index in 0016 can be applied.
    for journal in Journal.objects.filter(slug=''):
        base = slugify(journal.name) or f'journal-{journal.pk}'
        slug, n = base, 2
        while Journal.objects.filter(slug=slug).exclude(pk=journal.pk).exists():
            slug, n = f'{base}-{n}', n + 1
        journal.slug = slug
        journal.save(update_fields=['slug'])


def build_issues(apps, schema_editor):
    """Turn the free-text volume/issue on each article into a real Issue."""
    Article = apps.get_model('journalapp', 'Article')
    Issue = apps.get_model('journalapp', 'Issue')

    articles = Article.objects.exclude(journal__isnull=True).exclude(
        legacy_volume='', legacy_issue=''
    )
    for article in articles:
        volume = (article.legacy_volume or '').strip()
        number = (article.legacy_issue or '').strip()
        if not volume and not number:
            continue
        # An article with only an issue number still needs a volume to key on.
        volume = volume or '1'

        published = article.published_at or article.created_at
        issue, _ = Issue.objects.get_or_create(
            journal_id=article.journal_id, volume=volume, number=number,
            defaults={
                'year': published.year,
                'published_date': published.date(),
                'is_published': True,
            },
        )
        article.issue = issue
        article.save(update_fields=['issue'])


def migrate_archives(apps, schema_editor):
    """Copy ArchivedJournal rows into Issue before the model is dropped."""
    ArchivedJournal = apps.get_model('journalapp', 'ArchivedJournal')
    Journal = apps.get_model('journalapp', 'Journal')
    Issue = apps.get_model('journalapp', 'Issue')

    for archive in ArchivedJournal.objects.all():
        candidates = list(
            Journal.objects.filter(department_id=archive.department_id).order_by('order', 'pk')
        )
        if not candidates:
            continue
        journal = candidates[0]

        note = archive.description or ''
        if len(candidates) > 1:
            # The old model could not say which of a department's journals an
            # archive belonged to. Flag it rather than guess silently.
            note = (
                f'[Imported from the department archive — please confirm this '
                f'belongs to {journal.name}.]\n\n{note}'
            ).strip()

        volume = (archive.volume or '').strip() or '1'
        number = (archive.issue or '').strip()
        if Issue.objects.filter(journal=journal, volume=volume, number=number).exists():
            # Don't collide with an issue built from article metadata above.
            number = f'{number}-archive' if number else 'archive'

        Issue.objects.create(
            journal=journal,
            volume=volume,
            number=number,
            year=archive.publication_date.year,
            title=archive.title,
            description=note,
            document=archive.document,
            cover_image=archive.cover_image,
            published_date=archive.publication_date,
            is_published=True,
            featured=archive.featured,
            uploaded_by_id=archive.uploaded_by_id,
        )


def noop(apps, schema_editor):
    """Reversing leaves the data in place; the schema in 0016 is what unwinds."""


class Migration(migrations.Migration):

    dependencies = [
        ('journalapp', '0014_journal_top_level'),
    ]

    operations = [
        migrations.RunPython(seed_journals, noop),
        migrations.RunPython(build_issues, noop),
        migrations.RunPython(migrate_archives, noop),
    ]
