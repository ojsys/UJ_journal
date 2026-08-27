"""
The public face of a single journal.

Every view here resolves a journal by its slug and renders one part of that
journal's own site: home, editorial board, issues, an issue's table of contents,
a policy page. The portal used to expose journals only as a flat list under a
department, which could not distinguish two journals of the same department;
these views give each journal a self-contained home instead.

Nothing here requires a login — this is what a visitor sees.
"""
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .models import Article, EditorialBoardMember, Issue, Journal, JournalPage


def _get_journal(slug):
    """A published journal by slug, or 404. Inactive journals are hidden."""
    return get_object_or_404(Journal, slug=slug, is_active=True)


def _published_issues(journal):
    """Issues a visitor may see, newest edition first."""
    return journal.issues.filter(is_published=True)


# ---------------------------------------------------------------------------
# Journal landing pages
# ---------------------------------------------------------------------------

def journal_list(request):
    """The three journals, as cards. Entry point to everything below."""
    # annotate() groups the query, and Django drops Meta.ordering from grouped
    # queries — so every annotated queryset here re-states its order explicitly.
    journals = (
        Journal.objects.filter(is_active=True)
        .annotate(
            article_count=Count(
                'articles', filter=Q(articles__status='published'), distinct=True
            ),
            issue_count=Count(
                'issues', filter=Q(issues__is_published=True), distinct=True
            ),
        )
        .order_by('order', 'name')
    )
    return render(request, 'journalapp/journals/journal_list.html', {
        'journals': journals,
    })


def journal_home(request, slug):
    """A journal's home page: about it, its editors, its latest edition."""
    journal = _get_journal(slug)
    issues = _published_issues(journal)

    return render(request, 'journalapp/journals/journal_home.html', {
        'journal': journal,
        'latest_issue': issues.first(),
        'recent_issues': issues[:4],
        'issue_count': issues.count(),
        'lead_editors': journal.board_members.filter(
            is_active=True, section=EditorialBoardMember.SECTION_BOARD
        )[:4],
        'recent_articles': (
            Article.objects.filter(journal=journal, status='published')
            .select_related('author', 'issue')
            .order_by('-published_at')[:5]
        ),
        'rubrics': journal.rubrics.all(),
        'checklist_items': journal.checklist_items.filter(is_active=True),
    })


def journal_legacy_redirect(request, pk):
    """Permanent redirect from the old ``/journals/<pk>/`` links to the slug URL."""
    journal = get_object_or_404(Journal, pk=pk)
    return redirect('journal_home', slug=journal.slug, permanent=True)


# ---------------------------------------------------------------------------
# Editorial board
# ---------------------------------------------------------------------------

def journal_board(request, slug):
    """The journal's editorial board, grouped by section."""
    journal = _get_journal(slug)
    members = journal.board_members.filter(is_active=True)

    # Group in Python rather than one query per section: the board is a handful
    # of rows, and this keeps the section order defined by SECTION_CHOICES.
    grouped = []
    for code, label in EditorialBoardMember.SECTION_CHOICES:
        people = [m for m in members if m.section == code]
        if people:
            grouped.append({'label': label, 'members': people})

    return render(request, 'journalapp/journals/journal_board.html', {
        'journal': journal,
        'sections': grouped,
        'has_members': bool(grouped),
    })


# ---------------------------------------------------------------------------
# Issues (previous editions)
# ---------------------------------------------------------------------------

def journal_issues(request, slug):
    """Every published edition of this journal, for viewing and download."""
    journal = _get_journal(slug)
    issues = _published_issues(journal).annotate(
        article_count=Count('articles', filter=Q(articles__status='published'))
    ).order_by('-year', '-volume', '-number')

    # Group by year so the archive reads as "2026 / 2025 / …" like the client's
    # reference site, rather than one long undifferentiated list.
    by_year = []
    for issue in issues:
        if not by_year or by_year[-1]['year'] != issue.year:
            by_year.append({'year': issue.year, 'issues': []})
        by_year[-1]['issues'].append(issue)

    return render(request, 'journalapp/journals/journal_issues.html', {
        'journal': journal,
        'issue_years': by_year,
        'issue_count': len(issues),
    })


def issue_detail(request, slug, pk):
    """One edition: its table of contents plus the full-issue download."""
    journal = _get_journal(slug)
    issue = get_object_or_404(
        Issue, pk=pk, journal=journal, is_published=True
    )
    return render(request, 'journalapp/journals/issue_detail.html', {
        'journal': journal,
        'issue': issue,
        'articles': (
            issue.articles.filter(status='published')
            .select_related('author', 'category')
            .order_by('page_start', 'title')
        ),
    })


def all_issues(request):
    """Editions across every journal — the site-wide archive."""
    issues = (
        Issue.objects.filter(is_published=True, journal__is_active=True)
        .select_related('journal')
        .annotate(article_count=Count('articles', filter=Q(articles__status='published')))
        .order_by('-year', '-volume', '-number')
    )

    journal_slug = request.GET.get('journal')
    selected_journal = None
    if journal_slug:
        selected_journal = Journal.objects.filter(slug=journal_slug, is_active=True).first()
        if selected_journal:
            issues = issues.filter(journal=selected_journal)

    query = request.GET.get('q')
    if query:
        issues = issues.filter(
            Q(title__icontains=query)
            | Q(description__icontains=query)
            | Q(volume__icontains=query)
        )

    return render(request, 'journalapp/journals/all_issues.html', {
        'issues': issues,
        'journals': Journal.objects.filter(is_active=True),
        'selected_journal': selected_journal,
        'query': query or '',
    })


# ---------------------------------------------------------------------------
# Policy / guide pages
# ---------------------------------------------------------------------------

def journal_page(request, slug, page_slug):
    """A journal's own policy or guide page."""
    journal = _get_journal(slug)
    page = get_object_or_404(
        JournalPage, journal=journal, slug=page_slug, is_published=True
    )
    return render(request, 'journalapp/journals/journal_page.html', {
        'journal': journal,
        'page': page,
    })


# ---------------------------------------------------------------------------
# Submission entry point
# ---------------------------------------------------------------------------

def journal_submit(request, slug):
    """Send an author into the submission form with this journal pre-selected.

    The submission flow itself is unchanged (see ``submission_views.submission_create``);
    this only carries the journal choice across, so "Submit to JJEL" lands on a
    form that already knows which journal is meant.
    """
    journal = _get_journal(slug)
    target = f"{reverse('submission_create')}?journal={journal.pk}"
    if not request.user.is_authenticated:
        return redirect(f"{reverse('login')}?next={target}")
    return redirect(target)
