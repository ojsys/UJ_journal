"""
Load (or remove) realistic demo content for a live walkthrough with the client.

The point is to show what the three-journal portal can hold — editorial boards,
previous editions with downloadable PDFs, tables of contents, and per-journal
policy pages — without anyone having to type it all in first.

Everything this command creates is recorded in a manifest file, and ``--clear``
deletes exactly what is listed there and restores the journal profile fields it
overwrote. Nothing is matched by guesswork, so content the client adds during
the review is never touched.

    python manage.py journal_demo --load
    python manage.py journal_demo --status
    python manage.py journal_demo --clear

If the manifest is lost, ``--clear --force`` falls back to removing the known
demo records by name. That fallback is deliberately narrow: it only ever matches
the fixed names defined in this file.

EVERYTHING HERE IS FABRICATED — the editor names, affiliations, ISSNs, article
titles and abstracts are invented for the demo. Remove it with ``--clear``
before the site carries real content.
"""
import io
import json
from datetime import date

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from journalapp.models import (
    Article,
    EditorialBoardMember,
    Issue,
    Journal,
    JournalPage,
)
from django.contrib.auth import get_user_model

User = get_user_model()

MANIFEST_PATH = settings.BASE_DIR / '.journal_demo_manifest.json'
MANIFEST_VERSION = 1

#: The account demo articles are attributed to. Kept separate from any real
#: user so removing the demo cannot touch a genuine author's work.
DEMO_AUTHOR_EMAIL = 'demo.author@journal-demo.invalid'

#: Journal profile fields the demo overwrites. Their prior values are saved to
#: the manifest and restored on --clear.
PROFILE_FIELDS = (
    'about', 'issn_print', 'issn_online', 'published_by', 'contact_email',
)


# ---------------------------------------------------------------------------
# The demo content itself
# ---------------------------------------------------------------------------

PROFILES = {
    'jjel': {
        'about': (
            '<p><strong>The Jos Journal of the English Language (JJEL)</strong> is a '
            'non-commercial, university-based, peer-reviewed academic journal published '
            'by the Department of English, University of Jos.</p>'
            '<p>JJEL publishes original research in applied linguistics, syntax, '
            'phonology, discourse analysis, sociolinguistics and English language '
            'teaching, with particular interest in the English language as it is used, '
            'taught and adapted across Nigeria and the wider West African region.</p>'
            '<h3>Frequency</h3>'
            '<p>Two issues a year, in March and September.</p>'
        ),
        'issn_print': '2756-0114',
        'issn_online': '2756-0122',
        'published_by': 'Department of English, University of Jos',
        'contact_email': 'jjel@unijos.edu.ng',
    },
    'jojwol': {
        'about': (
            '<p><strong>The Jos Journal of Written and Oral Literature (JOJWOL)</strong> '
            'is a peer-reviewed journal published by the Department of English, '
            'University of Jos.</p>'
            '<p>JOJWOL is concerned with literature in both its written and its spoken '
            'forms: the novel, drama and poetry alongside oral narrative, praise poetry, '
            'folktale and performance. It welcomes work on African literatures in English '
            'and in translation, and on the relationship between oral tradition and the '
            'written text.</p>'
            '<h3>Frequency</h3>'
            '<p>One issue a year, in June.</p>'
        ),
        'issn_print': '2756-0130',
        'issn_online': '2756-0149',
        'published_by': 'Department of English, University of Jos',
        'contact_email': 'jojwol@unijos.edu.ng',
    },
    'humanity': {
        'about': (
            '<p><strong>Humanity Journal</strong> is a peer-reviewed, multidisciplinary '
            'journal published by the Department of General Studies, University of Jos.</p>'
            '<p>It publishes research across the humanities and the social sciences — '
            'history, philosophy, religious studies, sociology, peace and conflict '
            'studies — with an emphasis on scholarship that speaks to Nigerian and '
            'African social realities.</p>'
            '<h3>Frequency</h3>'
            '<p>Two issues a year, in April and October.</p>'
        ),
        'issn_print': '2756-0157',
        'issn_online': '2756-0165',
        'published_by': 'Department of General Studies, University of Jos',
        'contact_email': 'humanity@unijos.edu.ng',
    },
}

BOARD = {
    'jjel': [
        ('Prof. Ada N. Eze', 'Editor-in-Chief', 'board', 'University of Jos', 'a.eze@unijos.edu.ng'),
        ('Dr. Bala M. Yakubu', 'Managing Editor', 'board', 'University of Jos', 'b.yakubu@unijos.edu.ng'),
        ('Dr. Ngozi Okafor', 'Associate Editor', 'board', 'University of Jos', ''),
        ('Dr. Terlumun Agbe', 'Book Review Editor', 'board', 'University of Jos', ''),
        ('Prof. Samuel Adeyemi', 'Editorial Consultant', 'consultants', 'University of Ibadan', ''),
        ('Prof. Fatima Yusuf', 'Editorial Consultant', 'consultants', 'Ahmadu Bello University, Zaria', ''),
        ('Prof. Grace Nwankwo', 'Editorial Consultant', 'consultants', 'University of Nigeria, Nsukka', ''),
    ],
    'jojwol': [
        ('Prof. Emeka Obiora', 'Editor-in-Chief', 'board', 'University of Jos', 'e.obiora@unijos.edu.ng'),
        ('Dr. Halima Sani', 'Managing Editor', 'board', 'University of Jos', 'h.sani@unijos.edu.ng'),
        ('Dr. Joseph Dung', 'Associate Editor', 'board', 'University of Jos', ''),
        ('Prof. Kolade Ajayi', 'Editorial Consultant', 'consultants', 'Obafemi Awolowo University', ''),
        ('Prof. Mercy Ochieng', 'Editorial Consultant', 'consultants', 'University of Nairobi', ''),
    ],
    'humanity': [
        ('Prof. Yakubu D. Pam', 'Editor-in-Chief', 'board', 'University of Jos', 'y.pam@unijos.edu.ng'),
        ('Dr. Christiana Bitrus', 'Managing Editor', 'board', 'University of Jos', 'c.bitrus@unijos.edu.ng'),
        ('Dr. Ibrahim Danladi', 'Associate Editor', 'board', 'University of Jos', ''),
        ('Prof. Rosemary Uche', 'Editorial Consultant', 'consultants', 'University of Port Harcourt', ''),
        ('Prof. Aliyu Bello', 'Advisory Board Member', 'advisory', 'Bayero University, Kano', ''),
    ],
}

_SUBMISSION_GUIDE = (
    '<h3>Manuscript preparation</h3>'
    '<p>Manuscripts should be between 5,000 and 8,000 words including references, '
    'typed in Times New Roman 12pt, double spaced, on A4 paper with 1-inch margins.</p>'
    '<h3>Abstract and keywords</h3>'
    '<p>Every submission must carry an abstract of no more than 250 words, followed by '
    'four to six keywords.</p>'
    '<h3>Referencing</h3>'
    '<p>Use APA 7th edition throughout, for both in-text citation and the reference list.</p>'
    '<h3>Anonymity</h3>'
    '<p>Because review is double blind, the manuscript file must not carry the author\'s '
    'name, affiliation, or any self-identifying reference. Author details are collected '
    'separately during submission.</p>'
    '<h3>How to submit</h3>'
    '<p>Submit through this portal using the <em>Submit a paper</em> link above. You will '
    'be asked to confirm the journal\'s submission checklist before your manuscript is '
    'accepted into the review queue.</p>'
)

_REVIEW_POLICY = (
    '<p>Every manuscript submitted to this journal is subjected to <strong>double-blind '
    'peer review</strong>. Reviewers see the manuscript only by its identifier; they are '
    'never shown the author\'s name or affiliation, and authors are never told who '
    'reviewed their work.</p>'
    '<h3>The process</h3>'
    '<ol>'
    '<li><strong>Editorial screening.</strong> The editor checks scope, length and '
    'formatting. Manuscripts outside the journal\'s scope are returned without review.</li>'
    '<li><strong>Assignment.</strong> Two reviewers with relevant expertise are assigned.</li>'
    '<li><strong>Review.</strong> Reviewers assess the manuscript against the journal\'s '
    'published rubrics and recommend acceptance, revision, or rejection.</li>'
    '<li><strong>Decision.</strong> The Editor-in-Chief takes the final decision and '
    'communicates it to the author with the reviewers\' comments attached.</li>'
    '</ol>'
    '<h3>Turnaround</h3>'
    '<p>We aim to return a first decision within eight weeks of submission.</p>'
)

_PLAGIARISM_POLICY = (
    '<p>This journal takes plagiarism seriously in every form: verbatim copying, '
    'paraphrase without attribution, self-plagiarism, and the submission of work '
    'already published elsewhere.</p>'
    '<h3>Screening</h3>'
    '<p>All submissions are screened for similarity before they enter review. A '
    'similarity index above 20 per cent, excluding properly quoted and referenced '
    'material, results in rejection without further review.</p>'
    '<h3>After publication</h3>'
    '<p>Where plagiarism is established after publication, the article is retracted, a '
    'retraction notice is published in its place, and the author\'s institution is '
    'notified.</p>'
)

_OPEN_ACCESS = (
    '<p>This journal is fully open access. Every article it publishes is free to read, '
    'download and distribute from the moment of publication, with no subscription and no '
    'payment required from the reader.</p>'
    '<h3>Licensing</h3>'
    '<p>Articles are published under a Creative Commons Attribution licence (CC BY 4.0). '
    'Readers may share and adapt the work for any purpose, provided the original author '
    'and this journal are credited.</p>'
    '<h3>Cost to authors</h3>'
    '<p>Any publication charge is set by the journal and communicated on acceptance. It '
    'covers editorial handling and hosting only, and never influences the review decision.</p>'
)

_COPYRIGHT = (
    '<p>Authors retain copyright in their work. By publishing here, an author grants this '
    'journal the right of first publication and a non-exclusive licence to distribute the '
    'article under the terms of the journal\'s open access licence.</p>'
    '<p>Authors are free to deposit the published version in an institutional repository '
    'or on a personal website, provided the original publication in this journal is '
    'acknowledged with a full citation.</p>'
)


def _about_us(journal_name, description):
    return (
        f'<p><strong>{journal_name}</strong> {description}</p>'
        '<h3>Mission</h3>'
        '<p>To provide a rigorous, openly accessible venue for scholarship produced in '
        'Nigerian universities, and to hold that scholarship to the standards of '
        'international peer review.</p>'
        '<h3>Vision</h3>'
        '<p>To be recognised as a leading regional journal in its field, read and cited '
        'well beyond the institution that publishes it.</p>'
    )


PAGES = {
    'jjel': [
        ('About Us', 'about-us', _about_us(
            'The Jos Journal of the English Language',
            'is published twice yearly by the Department of English, University of Jos.')),
        ('Submission Guide', 'submission-guide', _SUBMISSION_GUIDE),
        ('Review Policy', 'review-policy', _REVIEW_POLICY),
        ('Plagiarism Policy', 'plagiarism-policy', _PLAGIARISM_POLICY),
        ('Open Access Policy', 'open-access-policy', _OPEN_ACCESS),
        ('Copyright Policy', 'copyright-policy', _COPYRIGHT),
    ],
    'jojwol': [
        ('About Us', 'about-us', _about_us(
            'The Jos Journal of Written and Oral Literature',
            'is published annually by the Department of English, University of Jos.')),
        ('Submission Guide', 'submission-guide', _SUBMISSION_GUIDE),
        ('Review Policy', 'review-policy', _REVIEW_POLICY),
        ('Plagiarism Policy', 'plagiarism-policy', _PLAGIARISM_POLICY),
    ],
    'humanity': [
        ('About Us', 'about-us', _about_us(
            'Humanity Journal',
            'is published twice yearly by the Department of General Studies, '
            'University of Jos.')),
        ('Submission Guide', 'submission-guide', _SUBMISSION_GUIDE),
        ('Review Policy', 'review-policy', _REVIEW_POLICY),
        ('Open Access Policy', 'open-access-policy', _OPEN_ACCESS),
    ],
}

#: journal slug -> list of issues. ``articles`` become that issue's table of
#: contents; an issue with none demonstrates the scanned-back-issue case, where
#: only the full-issue PDF exists.
ISSUES = {
    'jjel': [
        {
            'volume': '2', 'number': '1', 'year': 2026,
            'published_date': date(2026, 3, 15),
            'title': 'Language, Media and Identity',
            'description': (
                'A themed issue on language use across Nigerian broadcast and social '
                'media, and what it reveals about identity and audience.'
            ),
            'featured': True,
            'articles': [
                {
                    'title': 'Code-Switching in Nigerian Radio Broadcasting: A Discourse Analysis',
                    'keywords': 'code-switching, radio, Nigerian English, discourse analysis',
                    'pages': ('1', '18'),
                    'lead': 'how presenters on Nigerian radio move between English, Nigerian '
                            'Pidgin and indigenous languages within a single broadcast, and what '
                            'those shifts accomplish for the presenter and the audience',
                },
                {
                    'title': 'Pidgin as a Language of Solidarity in Northern Nigerian Campus Speech',
                    'keywords': 'Nigerian Pidgin, solidarity, campus speech, sociolinguistics',
                    'pages': ('19', '36'),
                    'lead': 'the social work done by Nigerian Pidgin among undergraduates in '
                            'Northern Nigeria, where it operates less as a lingua franca of '
                            'necessity than as a deliberate marker of belonging',
                },
                {
                    'title': 'Politeness Strategies in Nigerian WhatsApp Group Conversations',
                    'keywords': 'politeness, pragmatics, WhatsApp, computer-mediated communication',
                    'pages': ('37', '55'),
                    'lead': 'how politeness is negotiated in Nigerian WhatsApp groups, where the '
                            'absence of tone and gesture pushes speakers towards explicit '
                            'linguistic markers of deference and repair',
                },
            ],
        },
        {
            'volume': '1', 'number': '2', 'year': 2025,
            'published_date': date(2025, 9, 30),
            'title': '',
            'description': (
                'Back issue, digitised from the print edition. The complete issue is '
                'available as a single PDF.'
            ),
            'featured': False,
            'articles': [],
        },
    ],
    'jojwol': [
        {
            'volume': '1', 'number': '1', 'year': 2026,
            'published_date': date(2026, 6, 20),
            'title': 'Inaugural Issue',
            'description': (
                'The first issue of JOJWOL, opening with essays on the relationship '
                'between oral performance and the written text.'
            ),
            'featured': True,
            'articles': [
                {
                    'title': 'The Griot and the Novelist: Oral Memory in the West African Novel',
                    'keywords': 'oral tradition, griot, West African novel, memory',
                    'pages': ('1', '20'),
                    'lead': 'the debt the West African novel owes to the griot tradition, and '
                            'the ways novelists have carried the obligations of the oral '
                            'historian into printed narrative',
                },
                {
                    'title': 'Praise Poetry of the Berom: Form, Occasion and Performance',
                    'keywords': 'Berom, praise poetry, oral literature, performance',
                    'pages': ('21', '42'),
                    'lead': 'the formal structure of Berom praise poetry and its dependence on '
                            'occasion, arguing that the poem cannot be separated from the event '
                            'that calls it into being',
                },
                {
                    'title': 'Folktale Motifs in Contemporary Nigerian Children’s Writing',
                    'keywords': 'folktale, children’s literature, motif, adaptation',
                    'pages': ('43', '61'),
                    'lead': 'the survival and adaptation of traditional folktale motifs in '
                            'Nigerian writing for children published since 2000',
                },
            ],
        },
    ],
    'humanity': [
        {
            'volume': '3', 'number': '1', 'year': 2026,
            'published_date': date(2026, 4, 10),
            'title': '',
            'description': 'General issue.',
            'featured': True,
            'articles': [
                {
                    'title': 'Community Mediation and Conflict Resolution on the Jos Plateau',
                    'keywords': 'conflict resolution, mediation, Plateau State, peacebuilding',
                    'pages': ('1', '22'),
                    'lead': 'the record of community-led mediation on the Jos Plateau, and the '
                            'conditions under which locally brokered settlements have proved '
                            'more durable than externally imposed ones',
                },
                {
                    'title': 'Ethics and the Public Servant: A Philosophical Reappraisal',
                    'keywords': 'ethics, public service, moral philosophy, accountability',
                    'pages': ('23', '40'),
                    'lead': 'the moral obligations of the public servant, and whether the '
                            'language of accountability now used in Nigerian public life rests '
                            'on any coherent ethical foundation',
                },
            ],
        },
        {
            'volume': '2', 'number': '2', 'year': 2025,
            'published_date': date(2025, 10, 5),
            'title': '',
            'description': 'Back issue, available as a complete PDF.',
            'featured': False,
            'articles': [],
        },
    ],
}

_ABSTRACT = (
    '<p>This article examines {lead}. Drawing on material gathered between 2023 and '
    '2025, it argues that existing accounts have underplayed the role of context, and '
    'sets out an alternative reading supported by the evidence presented here. The '
    'discussion closes by considering what the findings imply for further research in '
    'the field, and for practice.</p>'
    '<p><em>This is placeholder text created for a demonstration of the portal.</em></p>'
)

_CONTENT = (
    '<h2>1. Introduction</h2>'
    '<p>This is demonstration content created to show how a published article appears '
    'in the portal. The layout, metadata, table-of-contents entry and PDF download all '
    'behave exactly as they will with real material.</p>'
    '<h2>2. Method</h2>'
    '<p>Data were gathered and analysed using established procedures in the field. A '
    'full account of the method would appear in this section.</p>'
    '<h2>3. Findings and discussion</h2>'
    '<p>Findings would be presented and interpreted here, with tables and figures as '
    'required.</p>'
    '<h2>4. Conclusion</h2>'
    '<p>The argument is drawn together and its implications set out.</p>'
    '<p><em>Placeholder text — remove with </em><code>python manage.py journal_demo --clear</code>.</p>'
)


# ---------------------------------------------------------------------------
# PDF generation — so the "Download PDF" buttons genuinely work in the demo
# ---------------------------------------------------------------------------

def build_issue_pdf(journal, issue_label, issue_title, contents):
    """Render a small cover-and-contents PDF for a demo issue.

    Uses xhtml2pdf, which the project already depends on for article PDFs
    (see ``views.article_pdf``). Returns bytes, or ``None`` if rendering fails —
    a missing PDF only means the download button is hidden, so it is never worth
    failing the whole seed over.
    """
    try:
        from xhtml2pdf import pisa
    except ImportError:
        return None

    rows = ''.join(
        f'<tr><td>{title}</td><td align="right">{pages}</td></tr>'
        for title, pages in contents
    ) or '<tr><td colspan="2">Full issue.</td></tr>'

    html = f"""
    <html><head><style>
      @page {{ size: a4 portrait; margin: 2.5cm; }}
      body {{ font-family: Helvetica, sans-serif; color: #1a1830; }}
      .kicker {{ font-size: 10pt; letter-spacing: 2px; color: #4f46e5; }}
      h1 {{ font-size: 22pt; margin: 6px 0 2px; }}
      h2 {{ font-size: 13pt; color: #4B4863; font-weight: normal; margin: 0 0 28px; }}
      .rule {{ border-bottom: 2px solid #4f46e5; margin: 0 0 22px; }}
      h3 {{ font-size: 11pt; letter-spacing: 1px; color: #4B4863; }}
      table {{ width: 100%; font-size: 10.5pt; }}
      td {{ padding: 5px 0; border-bottom: 0.5pt solid #E7E5EF; }}
      .note {{ margin-top: 40px; font-size: 8.5pt; color: #8B87A0; }}
    </style></head><body>
      <div class="kicker">{journal.name.upper()}</div>
      <h1>{issue_label}</h1>
      <h2>{issue_title or 'Complete issue'}</h2>
      <div class="rule"></div>
      <h3>CONTENTS</h3>
      <table>{rows}</table>
      <p class="note">
        Demonstration file generated by <code>manage.py journal_demo</code>.
        Not a real publication.
      </p>
    </body></html>
    """
    out = io.BytesIO()
    result = pisa.pisaDocument(io.BytesIO(html.encode('utf-8')), out)
    return None if result.err else out.getvalue()


# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------

class Manifest:
    """Record of everything the demo created, so --clear is exact."""

    def __init__(self):
        self.objects = []       # [{'model': 'journalapp.Issue', 'pk': 3}, ...]
        self.profiles = {}      # slug -> {field: original value}
        self.files = []         # media-relative paths to unlink

    def add(self, obj):
        self.objects.append({
            'model': f'{obj._meta.app_label}.{obj._meta.object_name}',
            'pk': obj.pk,
            'label': str(obj)[:120],
        })
        return obj

    def remember_profile(self, journal):
        self.profiles[journal.slug] = {f: getattr(journal, f) for f in PROFILE_FIELDS}

    def save(self):
        MANIFEST_PATH.write_text(json.dumps({
            'version': MANIFEST_VERSION,
            'created_at': timezone.now().isoformat(),
            'objects': self.objects,
            'profiles': self.profiles,
            'files': self.files,
        }, indent=2), encoding='utf-8')

    @staticmethod
    def load():
        if not MANIFEST_PATH.exists():
            return None
        data = json.loads(MANIFEST_PATH.read_text(encoding='utf-8'))
        if data.get('version') != MANIFEST_VERSION:
            raise CommandError(
                f'{MANIFEST_PATH} was written by a different version of this '
                f'command. Remove it and clear the demo content by hand.'
            )
        return data


# ---------------------------------------------------------------------------
# Command
# ---------------------------------------------------------------------------

class Command(BaseCommand):
    help = 'Load or remove demonstration content for the three journals.'

    def add_arguments(self, parser):
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument('--load', action='store_true',
                           help='Create the demo content.')
        group.add_argument('--clear', action='store_true',
                           help='Remove everything the last --load created.')
        group.add_argument('--status', action='store_true',
                           help='Report what is currently loaded.')
        parser.add_argument(
            '--force', action='store_true',
            help='With --clear, remove the known demo records even if the '
                 'manifest file is missing.')

    def handle(self, *args, **options):
        if options['status']:
            return self.show_status()
        if options['clear']:
            return self.clear(force=options['force'])
        return self.load()

    # -- status ------------------------------------------------------------

    def show_status(self):
        data = Manifest.load()
        if not data:
            self.stdout.write('No demo content is loaded (no manifest file).')
            self.stdout.write(f'Expected at: {MANIFEST_PATH}')
            return

        counts = {}
        for entry in data['objects']:
            counts[entry['model']] = counts.get(entry['model'], 0) + 1

        self.stdout.write(self.style.SUCCESS('Demo content is loaded.'))
        self.stdout.write(f"  Loaded at : {data['created_at']}")
        self.stdout.write(f"  Manifest  : {MANIFEST_PATH}")
        for model, n in sorted(counts.items()):
            self.stdout.write(f'  {model:<32} {n}')
        self.stdout.write(f"  Journal profiles modified: {len(data['profiles'])}")
        self.stdout.write(f"  Files written            : {len(data['files'])}")
        self.stdout.write('')
        self.stdout.write('Remove it with: python manage.py journal_demo --clear')

    # -- load --------------------------------------------------------------

    @transaction.atomic
    def load(self):
        if MANIFEST_PATH.exists():
            raise CommandError(
                'Demo content is already loaded. Run '
                '"python manage.py journal_demo --clear" first, or '
                '--status to see what is there.'
            )

        manifest = Manifest()
        author = self._demo_author(manifest)

        for slug in ('jjel', 'jojwol', 'humanity'):
            journal = Journal.objects.filter(slug=slug).first()
            if journal is None:
                self.stdout.write(self.style.WARNING(
                    f'  Skipped "{slug}" — no such journal in this database.'))
                continue

            self.stdout.write(self.style.MIGRATE_HEADING(f'\n{journal.name}'))
            self._load_profile(journal, manifest)
            self._load_board(journal, manifest)
            self._load_pages(journal, manifest)
            self._load_issues(journal, author, manifest)

        manifest.save()
        self._report_loaded(manifest)

    def _demo_author(self, manifest):
        """A dedicated account for demo articles, never a real user's."""
        author, created = User.objects.get_or_create(
            email=DEMO_AUTHOR_EMAIL,
            defaults={'first_name': 'Demo', 'last_name': 'Author'},
        )
        if created:
            # Unusable password: this account is for display, not for logging in.
            author.set_unusable_password()
            author.save()
            manifest.add(author)
        return author

    def _load_profile(self, journal, manifest):
        spec = PROFILES.get(journal.slug)
        if not spec:
            return
        manifest.remember_profile(journal)
        for field, value in spec.items():
            setattr(journal, field, value)
        journal.save(update_fields=list(spec))
        self.stdout.write('  profile     updated (about, ISSNs, contact)')

    def _load_board(self, journal, manifest):
        people = BOARD.get(journal.slug, [])
        for order, (name, position, section, affiliation, email) in enumerate(people):
            manifest.add(EditorialBoardMember.objects.create(
                journal=journal, name=name, position=position, section=section,
                affiliation=affiliation, email=email, order=order, is_active=True,
            ))
        self.stdout.write(f'  board       {len(people)} members')

    def _load_pages(self, journal, manifest):
        pages = PAGES.get(journal.slug, [])
        made = 0
        for order, (title, slug, content) in enumerate(pages):
            if JournalPage.objects.filter(journal=journal, slug=slug).exists():
                # The client may already have written this page — never overwrite it.
                continue
            manifest.add(JournalPage.objects.create(
                journal=journal, title=title, slug=slug, content=content,
                order=order, show_in_nav=True, is_published=True,
            ))
            made += 1
        skipped = len(pages) - made
        note = f' ({skipped} already existed, left alone)' if skipped else ''
        self.stdout.write(f'  pages       {made} created{note}')

    def _load_issues(self, journal, author, manifest):
        made_issues = made_articles = made_pdfs = 0

        for spec in ISSUES.get(journal.slug, []):
            if Issue.objects.filter(journal=journal, volume=spec['volume'],
                                    number=spec['number']).exists():
                # A real edition already occupies this volume/number.
                continue

            issue = manifest.add(Issue.objects.create(
                journal=journal,
                volume=spec['volume'], number=spec['number'], year=spec['year'],
                title=spec['title'], description=spec['description'],
                published_date=spec['published_date'],
                is_published=True, featured=spec['featured'],
            ))
            made_issues += 1

            contents = []
            for entry in spec['articles']:
                page_start, page_end = entry['pages']
                article = manifest.add(Article.objects.create(
                    title=entry['title'],
                    abstract=_ABSTRACT.format(lead=entry['lead']),
                    content=_CONTENT,
                    keywords=entry['keywords'],
                    author=author,
                    journal=journal,
                    issue=issue,
                    status='published',
                    published_at=timezone.make_aware(
                        timezone.datetime.combine(
                            spec['published_date'], timezone.datetime.min.time())
                    ),
                    page_start=page_start, page_end=page_end,
                ))
                made_articles += 1
                contents.append((entry['title'], f'{page_start}–{page_end}'))

            pdf = build_issue_pdf(journal, issue.label, spec['title'], contents)
            if pdf:
                name = f"demo-{journal.slug}-vol{spec['volume']}-{spec['number']}.pdf"
                issue.document.save(name, ContentFile(pdf), save=True)
                manifest.files.append(issue.document.name)
                made_pdfs += 1

        self.stdout.write(
            f'  issues      {made_issues} created, '
            f'{made_articles} articles, {made_pdfs} PDFs')

    def _report_loaded(self, manifest):
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f'Demo content loaded — {len(manifest.objects)} records, '
            f'{len(manifest.files)} PDFs.'))
        self.stdout.write(f'Manifest: {MANIFEST_PATH}')
        self.stdout.write('')
        self.stdout.write(self.style.WARNING(
            'Everything above is fabricated: the editor names, affiliations, '
            'ISSNs, article titles and abstracts are invented for the demo.'))
        self.stdout.write(self.style.WARNING(
            'The ISSNs in particular are placeholders, not registered numbers.'))
        self.stdout.write('')
        self.stdout.write('Walk the client through:')
        self.stdout.write('  /                                    three journal cards')
        self.stdout.write('  /journals/jjel/                      journal home, board, latest issue')
        self.stdout.write('  /journals/jjel/editorial-board/      editors and consultants')
        self.stdout.write('  /journals/jjel/issues/               previous editions by year')
        self.stdout.write('  /journals/jjel/p/submission-guide/   a policy page')
        self.stdout.write('  /archives/                           every issue, all journals')
        self.stdout.write('')
        self.stdout.write('Remove it all with: python manage.py journal_demo --clear')

    # -- clear -------------------------------------------------------------

    @transaction.atomic
    def clear(self, force=False):
        data = Manifest.load()
        if data is None:
            if not force:
                raise CommandError(
                    f'No manifest at {MANIFEST_PATH}, so there is no record of what '
                    f'the demo created. Re-run with --force to remove the known demo '
                    f'records by name instead.'
                )
            return self._clear_by_name()

        removed = self._delete_manifest_objects(data['objects'])
        restored = self._restore_profiles(data['profiles'])
        files = self._delete_files(data['files'])

        MANIFEST_PATH.unlink()
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f'Demo content removed — {removed} records deleted, '
            f'{restored} journal profiles restored, {files} files deleted.'))

    def _delete_manifest_objects(self, entries):
        """Delete recorded rows, most dependent first.

        Articles must go before the Issues they sit in (the FK is SET_NULL, so
        deleting the other way round would silently orphan them), and the demo
        author last of all.
        """
        order = [
            'journalapp.Article',
            'journalapp.Issue',
            'journalapp.EditorialBoardMember',
            'journalapp.JournalPage',
        ]
        by_model = {}
        for entry in entries:
            by_model.setdefault(entry['model'], []).append(entry['pk'])

        removed = 0
        for model_label in order + [m for m in by_model if m not in order]:
            pks = by_model.get(model_label)
            if not pks:
                continue
            from django.apps import apps
            try:
                model = apps.get_model(model_label)
            except LookupError:
                continue
            count = model.objects.filter(pk__in=pks).count()
            model.objects.filter(pk__in=pks).delete()
            removed += count
            missing = len(pks) - count
            note = f' ({missing} already gone)' if missing else ''
            self.stdout.write(f'  deleted {count:>3}  {model_label}{note}')
        return removed

    def _restore_profiles(self, profiles):
        restored = 0
        for slug, fields in profiles.items():
            journal = Journal.objects.filter(slug=slug).first()
            if journal is None:
                continue
            for field, value in fields.items():
                setattr(journal, field, value)
            journal.save(update_fields=list(fields))
            restored += 1
            self.stdout.write(f'  restored      profile of "{slug}"')
        return restored

    def _delete_files(self, names):
        from django.core.files.storage import default_storage
        deleted = 0
        for name in names:
            if default_storage.exists(name):
                default_storage.delete(name)
                deleted += 1
        if names:
            self.stdout.write(f'  deleted {deleted:>3}  demo PDFs')
        return deleted

    def _clear_by_name(self):
        """Fallback when the manifest is lost: match only the fixed demo names.

        Narrow on purpose — it can only ever match the constants defined at the
        top of this file, so content added during the review is untouched.
        """
        self.stdout.write(self.style.WARNING(
            'No manifest — removing the known demo records by name.'))

        board_names = [n for people in BOARD.values() for (n, *_rest) in people]
        article_titles = [
            entry['title']
            for issues in ISSUES.values()
            for spec in issues
            for entry in spec['articles']
        ]
        demo_issue_keys = [
            (slug, spec['volume'], spec['number'])
            for slug, issues in ISSUES.items()
            for spec in issues
        ]

        n_articles = Article.objects.filter(title__in=article_titles).delete()[0]

        issue_qs = Issue.objects.none()
        for slug, volume, number in demo_issue_keys:
            issue_qs = issue_qs | Issue.objects.filter(
                journal__slug=slug, volume=volume, number=number,
                document__startswith='issues/demo-',
            )
        n_issues = issue_qs.distinct().delete()[0]

        n_board = EditorialBoardMember.objects.filter(name__in=board_names).delete()[0]
        n_user = User.objects.filter(email=DEMO_AUTHOR_EMAIL).delete()[0]

        self.stdout.write(self.style.SUCCESS(
            f'Removed {n_articles} articles, {n_issues} issues, '
            f'{n_board} board members, {n_user} user rows.'))
        self.stdout.write(self.style.WARNING(
            'Journal profile text (about, ISSNs) and policy pages were NOT touched '
            '— without the manifest there is no way to tell demo text from the '
            "client's own edits. Review them by hand."))
