"""
Journal content management — the Chief Editor's tools for one journal.

Covers the journal's public profile, its editorial board, its issues (previous
editions), its policy pages, plus the review rubrics, submission checklist and
publication fee. All of it is per-journal, so every view here is gated with
``@journal_staff_required`` on ``CONTENT_ROLES``. Site staff pass through as
always.
"""
from django.contrib import messages
from django.db.models import Count
from django.utils import timezone
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required

from .models import (
    Journal, Rubric, ChecklistItem, JournalFee, Issue, EditorialBoardMember,
    JournalPage,
)
from .forms import (
    RubricForm, ChecklistItemForm, JournalFeeForm, JournalSettingsForm,
    IssueForm, EditorialBoardMemberForm, JournalPageForm,
)
from .permissions import journal_staff_required, journals_for, CONTENT_ROLES


# The policy pages a journal is normally expected to publish. Offered as
# one-click starters on the pages screen so an editor isn't staring at a
# blank form wondering what belongs here.
SUGGESTED_PAGES = (
    ('About Us', 'about-us'),
    ('Aims and Scope', 'aims-and-scope'),
    ('Submission Guide', 'submission-guide'),
    ('Review Policy', 'review-policy'),
    ('Open Access Policy', 'open-access-policy'),
    ('Plagiarism Policy', 'plagiarism-policy'),
    ('Copyright Policy', 'copyright-policy'),
    ('Contact Us', 'contact-us'),
)


# ---------------------------------------------------------------------------
# Management hub
# ---------------------------------------------------------------------------

@login_required
def journal_manage_list(request):
    """Journals the current user may manage — entry point to team/rubrics/checklist."""
    journals = (
        journals_for(request.user, roles=CONTENT_ROLES)
        .select_related('department')
        .prefetch_related('rubrics', 'checklist_items', 'issues', 'board_members', 'pages')
        .order_by('name')
    )
    if not journals.exists():
        raise PermissionDenied("You do not have a Chief Editor role on any journal.")

    return render(request, 'submissions/journal_manage_list.html', {
        'journals': journals,
    })


# ---------------------------------------------------------------------------
# Rubrics
# ---------------------------------------------------------------------------

@journal_staff_required(roles=CONTENT_ROLES, lookup='journal')
def journal_rubrics(request, pk):
    """List and add review rubrics for a journal."""
    journal = get_object_or_404(Journal, pk=pk)

    if request.method == 'POST':
        form = RubricForm(request.POST)
        if form.is_valid():
            rubric = form.save(commit=False)
            rubric.journal = journal
            rubric.save()
            messages.success(request, f'Rubric "{rubric.title}" added.')
            return redirect('journal_rubrics', pk=journal.pk)
    else:
        # Default the order to the end of the current list.
        next_order = journal.rubrics.count()
        form = RubricForm(initial={'order': next_order})

    return render(request, 'submissions/journal_rubrics.html', {
        'journal': journal,
        'rubrics': journal.rubrics.all(),
        'form': form,
    })


@journal_staff_required(roles=CONTENT_ROLES, lookup='journal')
def rubric_update(request, pk, rubric_id):
    journal = get_object_or_404(Journal, pk=pk)
    rubric = get_object_or_404(Rubric, pk=rubric_id, journal=journal)

    if request.method == 'POST':
        form = RubricForm(request.POST, instance=rubric)
        if form.is_valid():
            form.save()
            messages.success(request, 'Rubric updated.')
            return redirect('journal_rubrics', pk=journal.pk)
    else:
        form = RubricForm(instance=rubric)

    return render(request, 'submissions/rubric_form.html', {
        'journal': journal,
        'rubric': rubric,
        'form': form,
    })


@journal_staff_required(roles=CONTENT_ROLES, lookup='journal')
@require_POST
def rubric_delete(request, pk, rubric_id):
    journal = get_object_or_404(Journal, pk=pk)
    rubric = get_object_or_404(Rubric, pk=rubric_id, journal=journal)
    title = rubric.title
    rubric.delete()
    messages.success(request, f'Rubric "{title}" removed.')
    return redirect('journal_rubrics', pk=journal.pk)


# ---------------------------------------------------------------------------
# Submission checklist
# ---------------------------------------------------------------------------

@journal_staff_required(roles=CONTENT_ROLES, lookup='journal')
def journal_checklist(request, pk):
    """List and add checklist items for a journal."""
    journal = get_object_or_404(Journal, pk=pk)

    if request.method == 'POST':
        form = ChecklistItemForm(request.POST)
        if form.is_valid():
            item = form.save(commit=False)
            item.journal = journal
            item.save()
            messages.success(request, 'Checklist item added.')
            return redirect('journal_checklist', pk=journal.pk)
    else:
        next_order = journal.checklist_items.count()
        form = ChecklistItemForm(initial={
            'order': next_order, 'required': True, 'is_active': True,
        })

    return render(request, 'submissions/journal_checklist.html', {
        'journal': journal,
        'items': journal.checklist_items.all(),
        'form': form,
    })


@journal_staff_required(roles=CONTENT_ROLES, lookup='journal')
def checklist_item_update(request, pk, item_id):
    journal = get_object_or_404(Journal, pk=pk)
    item = get_object_or_404(ChecklistItem, pk=item_id, journal=journal)

    if request.method == 'POST':
        form = ChecklistItemForm(request.POST, instance=item)
        if form.is_valid():
            form.save()
            messages.success(request, 'Checklist item updated.')
            return redirect('journal_checklist', pk=journal.pk)
    else:
        form = ChecklistItemForm(instance=item)

    return render(request, 'submissions/checklist_item_form.html', {
        'journal': journal,
        'item': item,
        'form': form,
    })


@journal_staff_required(roles=CONTENT_ROLES, lookup='journal')
@require_POST
def checklist_item_delete(request, pk, item_id):
    """Delete a checklist item, or deactivate it if authors have answered it.

    A hard delete is blocked by ``on_delete=PROTECT`` on ChecklistResponse once
    any author has responded — deactivating keeps that history intact while
    hiding the item from new submissions.
    """
    journal = get_object_or_404(Journal, pk=pk)
    item = get_object_or_404(ChecklistItem, pk=item_id, journal=journal)

    if item.responses.exists():
        item.is_active = False
        item.save(update_fields=['is_active'])
        messages.info(
            request,
            'This item has author responses on record, so it was deactivated '
            '(hidden from new submissions) rather than deleted.'
        )
    else:
        item.delete()
        messages.success(request, 'Checklist item removed.')
    return redirect('journal_checklist', pk=journal.pk)


# ---------------------------------------------------------------------------
# Publication fee
# ---------------------------------------------------------------------------

@journal_staff_required(roles=CONTENT_ROLES, lookup='journal')
def journal_fee(request, pk):
    """Set (or clear) a journal's publication fee."""
    journal = get_object_or_404(Journal, pk=pk)
    fee, _ = JournalFee.objects.get_or_create(journal=journal)

    if request.method == 'POST':
        form = JournalFeeForm(request.POST, instance=fee)
        if form.is_valid():
            form.save()
            messages.success(request, 'Publication fee updated.')
            return redirect('journal_fee', pk=journal.pk)
    else:
        form = JournalFeeForm(instance=fee)

    return render(request, 'submissions/journal_fee.html', {
        'journal': journal,
        'fee': fee,
        'form': form,
    })


# ---------------------------------------------------------------------------
# Journal profile
# ---------------------------------------------------------------------------

@journal_staff_required(roles=CONTENT_ROLES, lookup='journal')
def journal_settings(request, pk):
    """Edit the journal's public profile — logo, about text, ISSNs, contact."""
    journal = get_object_or_404(Journal, pk=pk)

    if request.method == 'POST':
        form = JournalSettingsForm(request.POST, request.FILES, instance=journal)
        if form.is_valid():
            form.save()
            messages.success(request, f'{journal.short_name} updated.')
            return redirect('journal_settings', pk=journal.pk)
    else:
        form = JournalSettingsForm(instance=journal)

    return render(request, 'submissions/journal_settings.html', {
        'journal': journal,
        'form': form,
    })


# ---------------------------------------------------------------------------
# Issues (previous editions)
# ---------------------------------------------------------------------------

@journal_staff_required(roles=CONTENT_ROLES, lookup='journal')
def journal_issues_manage(request, pk):
    """List and add editions of a journal."""
    journal = get_object_or_404(Journal, pk=pk)

    if request.method == 'POST':
        form = IssueForm(request.POST, request.FILES, journal=journal)
        if form.is_valid():
            issue = form.save(commit=False)
            issue.journal = journal
            issue.uploaded_by = request.user
            issue.save()
            messages.success(request, f'{issue.label} added.')
            return redirect('journal_issues_manage', pk=journal.pk)
    else:
        form = IssueForm(journal=journal, initial={
            'year': timezone.now().year, 'published_date': timezone.now().date(),
            'is_published': True,
        })

    return render(request, 'submissions/journal_issues.html', {
        'journal': journal,
        'issues': journal.issues.annotate(article_count=Count('articles'))
                         .order_by('-year', '-volume', '-number'),
        'form': form,
    })


@journal_staff_required(roles=CONTENT_ROLES, lookup='journal')
def issue_update(request, pk, issue_id):
    journal = get_object_or_404(Journal, pk=pk)
    issue = get_object_or_404(Issue, pk=issue_id, journal=journal)

    if request.method == 'POST':
        form = IssueForm(request.POST, request.FILES, instance=issue, journal=journal)
        if form.is_valid():
            form.save()
            messages.success(request, f'{issue.label} updated.')
            return redirect('journal_issues_manage', pk=journal.pk)
    else:
        form = IssueForm(instance=issue, journal=journal)

    return render(request, 'submissions/issue_form.html', {
        'journal': journal,
        'issue': issue,
        'form': form,
    })


@journal_staff_required(roles=CONTENT_ROLES, lookup='journal')
@require_POST
def issue_delete(request, pk, issue_id):
    """Delete an edition, unless articles have been published into it.

    Deleting would silently detach those articles (the FK is SET_NULL), losing
    which edition they appeared in — so refuse and let the editor move them first.
    """
    journal = get_object_or_404(Journal, pk=pk)
    issue = get_object_or_404(Issue, pk=issue_id, journal=journal)

    article_count = issue.articles.count()
    if article_count:
        messages.error(
            request,
            f'{issue.label} still has {article_count} article'
            f'{"s" if article_count != 1 else ""} in it. Move them to another '
            f'edition first, or unpublish this one to hide it.'
        )
    else:
        label = issue.label
        issue.delete()
        messages.success(request, f'{label} removed.')
    return redirect('journal_issues_manage', pk=journal.pk)


# ---------------------------------------------------------------------------
# Editorial board
# ---------------------------------------------------------------------------

@journal_staff_required(roles=CONTENT_ROLES, lookup='journal')
def journal_board_manage(request, pk):
    """List and add members of a journal's public editorial board."""
    journal = get_object_or_404(Journal, pk=pk)

    if request.method == 'POST':
        form = EditorialBoardMemberForm(request.POST, request.FILES)
        if form.is_valid():
            member = form.save(commit=False)
            member.journal = journal
            member.save()
            messages.success(request, f'{member.name} added to the board.')
            return redirect('journal_board_manage', pk=journal.pk)
    else:
        form = EditorialBoardMemberForm(initial={
            'order': journal.board_members.count(), 'is_active': True,
        })

    return render(request, 'submissions/journal_board.html', {
        'journal': journal,
        'members': journal.board_members.all(),
        'form': form,
    })


@journal_staff_required(roles=CONTENT_ROLES, lookup='journal')
def board_member_update(request, pk, member_id):
    journal = get_object_or_404(Journal, pk=pk)
    member = get_object_or_404(EditorialBoardMember, pk=member_id, journal=journal)

    if request.method == 'POST':
        form = EditorialBoardMemberForm(request.POST, request.FILES, instance=member)
        if form.is_valid():
            form.save()
            messages.success(request, f'{member.name} updated.')
            return redirect('journal_board_manage', pk=journal.pk)
    else:
        form = EditorialBoardMemberForm(instance=member)

    return render(request, 'submissions/board_member_form.html', {
        'journal': journal,
        'member': member,
        'form': form,
    })


@journal_staff_required(roles=CONTENT_ROLES, lookup='journal')
@require_POST
def board_member_delete(request, pk, member_id):
    journal = get_object_or_404(Journal, pk=pk)
    member = get_object_or_404(EditorialBoardMember, pk=member_id, journal=journal)
    name = member.name
    member.delete()
    messages.success(request, f'{name} removed from the board.')
    return redirect('journal_board_manage', pk=journal.pk)


# ---------------------------------------------------------------------------
# Policy and guide pages
# ---------------------------------------------------------------------------

@journal_staff_required(roles=CONTENT_ROLES, lookup='journal')
def journal_pages_manage(request, pk):
    """List and add a journal's policy/guide pages."""
    journal = get_object_or_404(Journal, pk=pk)

    if request.method == 'POST':
        form = JournalPageForm(request.POST, journal=journal)
        if form.is_valid():
            page = form.save(commit=False)
            page.journal = journal
            page.save()
            messages.success(request, f'"{page.title}" added.')
            return redirect('journal_pages_manage', pk=journal.pk)
    else:
        form = JournalPageForm(journal=journal, initial={
            'order': journal.pages.count(), 'show_in_nav': True, 'is_published': True,
        })

    return render(request, 'submissions/journal_pages.html', {
        'journal': journal,
        'pages': journal.pages.all(),
        'form': form,
        'suggested_pages': SUGGESTED_PAGES,
    })


@journal_staff_required(roles=CONTENT_ROLES, lookup='journal')
def journal_page_update(request, pk, page_id):
    journal = get_object_or_404(Journal, pk=pk)
    page = get_object_or_404(JournalPage, pk=page_id, journal=journal)

    if request.method == 'POST':
        form = JournalPageForm(request.POST, instance=page, journal=journal)
        if form.is_valid():
            form.save()
            messages.success(request, f'"{page.title}" updated.')
            return redirect('journal_pages_manage', pk=journal.pk)
    else:
        form = JournalPageForm(instance=page, journal=journal)

    return render(request, 'submissions/journal_page_form.html', {
        'journal': journal,
        'page': page,
        'form': form,
    })


@journal_staff_required(roles=CONTENT_ROLES, lookup='journal')
@require_POST
def journal_page_delete(request, pk, page_id):
    journal = get_object_or_404(Journal, pk=pk)
    page = get_object_or_404(JournalPage, pk=page_id, journal=journal)
    title = page.title
    page.delete()
    messages.success(request, f'"{title}" removed.')
    return redirect('journal_pages_manage', pk=journal.pk)
