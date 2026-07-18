"""
Seed two sample published articles on the theme "How AI is affecting Education".

Idempotent: running it repeatedly will not create duplicates — it matches
articles by title and refreshes their content each run.

Usage:
    python manage.py seed_ai_articles
    python manage.py seed_ai_articles --author-email someone@unijos.edu.ng
    python manage.py seed_ai_articles --unpublish     # create as drafts instead
"""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from journalapp.models import (
    Article,
    ArticleCategory,
    ArticleLog,
    Department,
    Journal,
)

User = get_user_model()


ARTICLES = [
    {
        "title": "How Artificial Intelligence Is Reshaping the Modern Classroom",
        "keywords": "artificial intelligence, education, personalised learning, "
                    "intelligent tutoring, EdTech, generative AI",
        "volume": "1", "issue": "1", "page_start": "1", "page_end": "14",
        "doi": "10.5555/unijos.ai.edu.2026.001",
        "abstract": (
            "<p>Artificial intelligence (AI) is moving from the periphery of "
            "educational technology to the centre of teaching and learning. This "
            "article examines how AI-powered tools &mdash; from intelligent tutoring "
            "systems to automated feedback and adaptive learning platforms &mdash; are "
            "reshaping the roles of teachers and learners. Drawing on recent advances "
            "in generative AI, we discuss opportunities for personalised instruction, "
            "the reduction of administrative burden on educators, and wider access to "
            "quality learning resources, while also weighing the risks of over-reliance, "
            "algorithmic bias, and the deepening of the digital divide.</p>"
        ),
        "content": (
            "<h2>1. Introduction</h2>"
            "<p>For decades, the promise of technology in education outpaced its "
            "impact in the classroom. That gap is now closing. Modern AI systems can "
            "understand natural language, generate explanations, and adapt to an "
            "individual learner in real time &mdash; capabilities that touch the core "
            "of teaching rather than merely its logistics.</p>"

            "<h2>2. Personalised and adaptive learning</h2>"
            "<p>Adaptive platforms adjust the difficulty, pace, and sequence of "
            "material to each student. Instead of a single lecture for thirty "
            "learners, an AI tutor can offer thirty parallel paths, revisiting weak "
            "areas and accelerating through mastered ones. Early evidence suggests "
            "this can narrow attainment gaps when it is paired with, rather than a "
            "substitute for, skilled teaching.</p>"

            "<h2>3. Lightening the teacher's load</h2>"
            "<p>Much of a teacher's week is spent on tasks that do not require a "
            "human expert: drafting quizzes, marking multiple-choice work, writing "
            "routine feedback, and preparing materials. Generative AI can produce "
            "first drafts of all of these in seconds, freeing educators to spend "
            "their time on mentoring, discussion, and the relational work that "
            "machines cannot do.</p>"

            "<h2>4. Access and equity</h2>"
            "<p>AI tutoring available on a low-cost phone could bring one-to-one "
            "support to learners who have never had access to it. Yet the same "
            "technology can widen inequality if reliable devices, electricity, and "
            "connectivity remain unevenly distributed. Equity must be designed in, "
            "not assumed.</p>"

            "<h2>5. Risks and responsibilities</h2>"
            "<p>Three concerns recur: bias inherited from training data, the erosion "
            "of independent thinking when answers are always a prompt away, and the "
            "privacy of student data. Responsible adoption means transparency about "
            "how tools work, human oversight of high-stakes decisions, and teaching "
            "students to use AI critically.</p>"

            "<h2>6. Conclusion</h2>"
            "<p>AI will not replace teachers, but teachers who use AI well are likely "
            "to replace those who do not. The task for institutions is to steer the "
            "technology toward deeper learning and greater access, while guarding "
            "against its failure modes.</p>"
        ),
    },
    {
        "title": "AI, Academic Integrity and the Future of Assessment in Higher Education",
        "keywords": "generative AI, academic integrity, assessment, higher education, "
                    "ChatGPT, plagiarism, authentic assessment",
        "volume": "1", "issue": "1", "page_start": "15", "page_end": "29",
        "doi": "10.5555/unijos.ai.edu.2026.002",
        "abstract": (
            "<p>The public release of powerful generative AI systems has forced "
            "universities to confront urgent questions about academic integrity and "
            "the validity of traditional assessment. This paper explores how tools "
            "that produce fluent essays, solve problem sets, and write code challenge "
            "long-standing assumptions about how student learning is measured. Rather "
            "than framing AI purely as a threat, we argue for a redesign of assessment "
            "toward authentic, process-oriented, and AI-aware tasks, and we outline "
            "practical policies that balance innovation with fairness.</p>"
        ),
        "content": (
            "<h2>1. A sudden challenge</h2>"
            "<p>Almost overnight, students gained access to systems that can complete "
            "many conventional assignments to a passing standard. Take-home essays, "
            "short-answer questions, and introductory coding tasks &mdash; staples of "
            "university assessment &mdash; are now trivially automatable.</p>"

            "<h2>2. Why detection is not the answer</h2>"
            "<p>AI-detection tools are unreliable and disproportionately flag "
            "non-native English writers, creating fairness problems of their own. An "
            "arms race between generators and detectors is unwinnable and corrosive to "
            "trust. Integrity policy cannot rest on catching machines.</p>"

            "<h2>3. Redesigning assessment</h2>"
            "<p>The durable response is to assess what AI cannot easily fake: the "
            "process of learning. Oral defences, in-class writing, iterative drafts "
            "with visible revision history, personal reflection tied to local context, "
            "and project work reviewed at checkpoints all shift the emphasis from the "
            "final artefact to the student's demonstrated understanding.</p>"

            "<h2>4. Teaching with AI, not against it</h2>"
            "<p>Many programmes are moving toward &lsquo;AI-aware&rsquo; tasks in which "
            "students use AI openly, then critique, correct, and extend its output. "
            "This builds the judgement graduates will need in workplaces where such "
            "tools are ubiquitous, while making the student's own contribution the "
            "object of assessment.</p>"

            "<h2>5. Policy and fairness</h2>"
            "<p>Clear, course-level rules &mdash; stating where AI use is permitted, "
            "required, or prohibited &mdash; reduce ambiguity and protect students. "
            "Policies should be consistent, communicated in advance, and mindful that "
            "unequal access to premium AI tools can itself become a source of "
            "inequity.</p>"

            "<h2>6. Conclusion</h2>"
            "<p>Generative AI exposes assessment practices that were already weak "
            "proxies for learning. Handled well, it is an invitation to make "
            "assessment more authentic, more humane, and more honest.</p>"
        ),
    },
]


class Command(BaseCommand):
    help = 'Seed two sample published articles about how AI is affecting education.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--author-email',
            help='Email of an existing user to set as the author. '
                 'Defaults to the first staff/superuser (or creates an editorial user).',
        )
        parser.add_argument(
            '--unpublish',
            action='store_true',
            help='Create the articles as drafts instead of published.',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        author = self._get_author(options.get('author_email'))
        journal = self._get_journal()
        category = self._get_category(journal)
        publish = not options['unpublish']

        self.stdout.write(f'Author : {author.get_full_name() or author.email}')
        self.stdout.write(f'Journal: {journal.name}')
        self.stdout.write('')

        for data in ARTICLES:
            article, created = Article.objects.get_or_create(
                title=data['title'],
                defaults={'author': author, 'journal': journal},
            )
            article.author = article.author or author
            article.journal = journal
            article.category = category
            article.abstract = data['abstract']
            article.content = data['content']
            article.keywords = data['keywords']
            article.volume = data['volume']
            article.issue = data['issue']
            article.page_start = data['page_start']
            article.page_end = data['page_end']
            article.doi = data['doi']

            if publish:
                article.status = 'published'
                if not article.published_at:
                    article.published_at = timezone.now()
            else:
                article.status = 'draft'
                article.published_at = None
            article.save()

            ArticleLog.objects.create(
                article=article,
                user=author,
                action='Article created via seed' if created else 'Article refreshed via seed',
                notes='seed_ai_articles management command',
            )

            verb = 'Created' if created else 'Updated'
            state = article.get_status_display()
            self.stdout.write(self.style.SUCCESS(f'  {verb} [{state}] — {article.title}'))

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('Done. 2 sample AI-in-education articles seeded.'))

    # ---- helpers -------------------------------------------------------------

    def _get_author(self, email):
        if email:
            try:
                return User.objects.get(email=email)
            except User.DoesNotExist:
                self.stderr.write(self.style.WARNING(
                    f'No user with email {email}; falling back to a default author.'))
        author = (User.objects.filter(is_superuser=True).first()
                  or User.objects.filter(is_staff=True).first()
                  or User.objects.first())
        if author:
            return author
        # No users at all — create a non-login editorial author.
        author = User.objects.create_user(
            email='editorial@unijos.edu.ng',
            first_name='Editorial',
            last_name='Board',
        )
        self.stdout.write('Created editorial author user (editorial@unijos.edu.ng).')
        return author

    def _get_journal(self):
        journal = Journal.objects.first()
        if journal:
            return journal
        dept, _ = Department.objects.get_or_create(
            code='EDU',
            defaults={
                'name': 'Faculty of Education',
                'description': 'Research on teaching, learning and educational technology.',
            },
        )
        return Journal.objects.create(
            department=dept,
            name='Journal of Educational Technology',
            description='Peer-reviewed research on technology in education.',
        )

    def _get_category(self, journal):
        category, _ = ArticleCategory.objects.get_or_create(
            journal=journal,
            name='Educational Technology',
            defaults={'description': 'Articles on technology in teaching and learning.'},
        )
        return category
