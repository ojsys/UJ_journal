"""
Views for the article submission workflow system.

This module contains all views related to:
- Author submissions
- Admin management of submissions
- Reviewer/Editor assignment and feedback
- Chat/messaging system
- Document extraction and publishing
"""

from django.core.exceptions import PermissionDenied
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST, require_GET
from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.utils import timezone
from django.urls import reverse
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings

import docx
import io
import re
import logging

logger = logging.getLogger('journalapp')

from .models import (
    Submission, Assignment, SubmissionMessage, DocumentVersion, SubmissionLog,
    Article, Journal, Profile, GuestReviewer, CustomUser, JournalRole,
    ChecklistItem, ChecklistResponse, ReviewRound
)
from .permissions import (
    journal_staff_required, journals_for, has_journal_role,
    CONTENT_ROLES, WORKFLOW_ROLES, DECISION_ROLES,
)
from .utils import get_from_email
from .forms import (
    SubmissionForm, SubmissionEditForm, SubmissionAssignmentForm,
    AssignmentFeedbackForm, SubmissionMessageForm, DocumentVersionForm,
    FinalDocumentUploadForm, ReviewCopyUploadForm, PublishArticleForm,
    RevisionRequestForm, GuestReviewerForm, BulkGuestReviewerForm,
    AssignGuestReviewerForm, JournalRoleForm
)


# ============================================================================
# Helper Functions
# ============================================================================

def log_submission_action(submission, user, action, details=None):
    """Create a log entry for a submission action"""
    SubmissionLog.objects.create(
        submission=submission,
        user=user,
        action=action,
        details=details or {}
    )


def extract_document_content(file):
    """
    Extract structured content from a Word document.
    Returns a dictionary with title, abstract, keywords, content, and citations.
    """
    try:
        doc = docx.Document(io.BytesIO(file.read()))

        # Extract all paragraphs
        paragraphs = []
        current_section = 'content'
        sections = {
            'title': '',
            'abstract': '',
            'keywords': '',
            'content': '',
            'citations': ''
        }

        for para in doc.paragraphs:
            text = para.text.strip()
            if not text:
                continue

            # Check for section headings
            lower_text = text.lower()

            # Title is usually the first non-empty paragraph with Heading style
            if not sections['title']:
                if para.style.name.startswith('Heading') or para.runs and para.runs[0].bold:
                    sections['title'] = text
                    continue
                else:
                    sections['title'] = text
                    continue

            # Detect section changes
            if lower_text in ['abstract', 'summary']:
                current_section = 'abstract'
                continue
            elif lower_text.startswith('keyword') or lower_text.startswith('key word'):
                current_section = 'keywords'
                continue
            elif lower_text in ['references', 'bibliography', 'citations', 'works cited']:
                current_section = 'citations'
                continue
            elif lower_text in ['introduction', 'background', 'methods', 'methodology',
                               'results', 'discussion', 'conclusion', 'conclusions']:
                current_section = 'content'

            # Add text to appropriate section
            if current_section == 'abstract':
                sections['abstract'] += text + '\n'
            elif current_section == 'keywords':
                # Extract keywords (usually comma or semicolon separated)
                sections['keywords'] = text
            elif current_section == 'citations':
                sections['citations'] += text + '\n'
            else:
                sections['content'] += text + '\n\n'

        # Clean up sections
        for key in sections:
            sections[key] = sections[key].strip()

        return sections

    except Exception as e:
        return {
            'error': str(e),
            'title': '',
            'abstract': '',
            'keywords': '',
            'content': '',
            'citations': ''
        }


# ============================================================================
# Author Views
# ============================================================================

@login_required
def submission_create(request):
    """Allow authors to submit a new article"""
    checklist_error = None
    checked_ids = set()
    if request.method == 'POST':
        form = SubmissionForm(request.POST, request.FILES)
        # Remember which boxes were ticked so a validation error doesn't wipe them.
        checked_ids = {
            int(key.split('checklist_', 1)[1])
            for key in request.POST
            if key.startswith('checklist_') and key.split('checklist_', 1)[1].isdigit()
        }
        # Validate the selected journal's required checklist items before saving.
        # This runs alongside the form so both sets of errors show at once.
        selected_journal = form.data.get('journal')
        required_items = ChecklistItem.objects.filter(
            journal_id=selected_journal, is_active=True, required=True
        ) if selected_journal else ChecklistItem.objects.none()
        unticked = [item for item in required_items if item.pk not in checked_ids]
        if unticked:
            checklist_error = 'Please confirm every required checklist item before submitting.'

        if form.is_valid() and not checklist_error:
            submission = form.save(commit=False)
            submission.author = request.user
            # Auto-generate title from filename (without extension)
            if not submission.title and submission.document:
                filename = submission.document.name
                # Remove extension and clean up the name
                title = filename.rsplit('.', 1)[0]
                title = title.replace('_', ' ').replace('-', ' ')
                submission.title = title[:300]  # Truncate to max length
            submission.save()

            # Record the author's checklist responses (active items for this
            # journal), freezing the wording onto each response.
            active_items = submission.journal.checklist_items.filter(is_active=True)
            ChecklistResponse.objects.bulk_create([
                ChecklistResponse(
                    submission=submission,
                    item=item,
                    item_text=item.text,
                    checked=bool(request.POST.get(f'checklist_{item.pk}')),
                )
                for item in active_items
            ])

            # Create initial document version
            DocumentVersion.objects.create(
                submission=submission,
                uploaded_by=request.user,
                document=submission.document,
                version_number=1,
                notes='Initial submission'
            )

            # Log the action
            log_submission_action(
                submission, request.user, 'Submission created',
                {'title': submission.title}
            )

            messages.success(request, 'Your article has been submitted successfully! You will be notified when it is reviewed.')
            return redirect('submission_list')
    else:
        form = SubmissionForm()

    # Get all journals for card display, each with its active checklist items so
    # the form can reveal the right checklist for the chosen journal.
    journals = Journal.objects.all().order_by('name').prefetch_related('checklist_items')

    return render(request, 'submissions/submission_form.html', {
        'form': form,
        'title': 'Submit New Article',
        'journals': journals,
        'checklist_error': checklist_error,
        'checked_ids': checked_ids,
    })


@login_required
def submission_list(request):
    """List all submissions for the current author.

    No status filter here by design — authors track a submission from its detail
    page (the activity timeline), so the list is just the full record with a
    passive status pill per row.
    """
    submissions = Submission.objects.filter(
        author=request.user
    ).select_related('journal').order_by('-submitted_at')

    paginator = Paginator(submissions, 10)
    page = request.GET.get('page')
    submissions = paginator.get_page(page)

    return render(request, 'submissions/submission_list.html', {
        'submissions': submissions,
    })


@login_required
def submission_detail(request, pk):
    """View submission details (for author)"""
    submission = get_object_or_404(Submission, pk=pk)

    # Check permission - author can view their own; site staff and this
    # journal's editorial team can view all; assignees are checked below.
    if (submission.author != request.user
            and not has_journal_role(request.user, submission.journal, roles=WORKFLOW_ROLES)):
        # Check if user is assigned to this submission
        if not submission.assignments.filter(assigned_to=request.user).exists():
            messages.error(request, 'You do not have permission to view this submission.')
            return redirect('submission_list')

    # Get activity log
    logs = submission.logs.all()[:20]

    # Get document versions
    versions = submission.document_versions.all()

    # Get completed assignments with feedback (for author to see reviewer feedback)
    completed_assignments = submission.assignments.filter(
        status='completed'
    ).select_related('assigned_to').order_by('completed_at')

    return render(request, 'submissions/submission_detail.html', {
        'submission': submission,
        'logs': logs,
        'versions': versions,
        'completed_assignments': completed_assignments,
    })


@login_required
def submission_edit(request, pk):
    """Let an author correct their submission until an editor decides on it.

    Distinct from ``submission_revise``: this is for fixing a mistake (wrong
    file, typo in the cover letter) without signalling a formal revision, so it
    does not change the status. Replacing the file adds a new DocumentVersion so
    the author never has to juggle multiple uploads, while history is preserved.
    """
    submission = get_object_or_404(Submission, pk=pk, author=request.user)

    if not submission.is_editable_by_author:
        messages.error(
            request,
            'This submission can no longer be edited — an editor has already '
            'taken a decision on it.'
        )
        return redirect('submission_detail', pk=pk)

    if request.method == 'POST':
        form = SubmissionEditForm(request.POST, request.FILES, instance=submission)
        if form.is_valid():
            submission = form.save()

            new_document = form.cleaned_data.get('new_document')
            if new_document:
                version = DocumentVersion.objects.create(
                    submission=submission,
                    uploaded_by=request.user,
                    document=new_document,
                    notes='Author replaced the manuscript',
                )
                submission.document = new_document
                submission.save(update_fields=['document'])
                log_submission_action(
                    submission, request.user, 'Author replaced the manuscript',
                    {'version': version.version_number}
                )
            else:
                log_submission_action(
                    submission, request.user, 'Author edited submission details'
                )

            messages.success(request, 'Your submission has been updated.')
            return redirect('submission_detail', pk=pk)
    else:
        form = SubmissionEditForm(instance=submission)

    return render(request, 'submissions/submission_edit.html', {
        'form': form,
        'submission': submission,
    })


@login_required
def submission_revise(request, pk):
    """Allow author to submit a revised document"""
    submission = get_object_or_404(Submission, pk=pk, author=request.user)

    if submission.status != 'revision_requested':
        messages.error(request, 'This submission is not awaiting revisions.')
        return redirect('submission_detail', pk=pk)

    if request.method == 'POST':
        form = DocumentVersionForm(request.POST, request.FILES)
        if form.is_valid():
            version = form.save(commit=False)
            version.submission = submission
            version.uploaded_by = request.user
            version.save()

            # Update submission status
            submission.status = 'revised'
            submission.document = version.document
            submission.save()

            # Log the action
            log_submission_action(
                submission, request.user, 'Revised document submitted',
                {'version': version.version_number}
            )

            messages.success(request, 'Your revised document has been submitted.')
            return redirect('submission_detail', pk=pk)
    else:
        form = DocumentVersionForm()

    return render(request, 'submissions/submission_revise.html', {
        'form': form,
        'submission': submission
    })


# ============================================================================
# Admin Views
# ============================================================================

@journal_staff_required(roles=WORKFLOW_ROLES, lookup='none')
def admin_submission_list(request):
    """Admin view to see all submissions"""
    # Scope to journals this user has an editorial role on. Site staff get every
    # journal back from journals_for(), so this is a no-op for them.
    permitted_journals = journals_for(request.user, roles=WORKFLOW_ROLES)
    scoped = Submission.objects.filter(journal__in=permitted_journals)
    submissions = scoped.select_related('author', 'journal')

    # Filter by status
    status_filter = request.GET.get('status')
    if status_filter:
        submissions = submissions.filter(status=status_filter)

    # Filter by journal — bounded by the permitted set above, so a hand-typed
    # ?journal= for someone else's journal returns nothing rather than leaking.
    journal_filter = request.GET.get('journal')
    if journal_filter:
        submissions = submissions.filter(journal_id=journal_filter)

    # Search
    search_query = request.GET.get('q')
    if search_query:
        submissions = submissions.filter(
            Q(title__icontains=search_query) |
            Q(author__first_name__icontains=search_query) |
            Q(author__last_name__icontains=search_query) |
            Q(author__email__icontains=search_query)
        )

    submissions = submissions.order_by('-submitted_at')

    paginator = Paginator(submissions, 20)
    page = request.GET.get('page')
    submissions = paginator.get_page(page)

    # Get counts by status
    status_counts = scoped.values('status').annotate(count=Count('id'))

    # Get detailed status breakdowns
    status_details = {}

    # Pending - need assignment
    pending_subs = scoped.filter(status='pending').select_related('author', 'journal').order_by('-submitted_at')[:5]
    status_details['pending'] = {
        'count': pending_subs.count(),
        'submissions': pending_subs,
        'label': 'Pending Review',
        'icon': 'clock',
        'color': 'warning'
    }

    # In Review - awaiting reviewer feedback
    in_review_subs = scoped.filter(status='in_review').select_related('author', 'journal').prefetch_related('assignments').order_by('-submitted_at')[:5]
    status_details['in_review'] = {
        'count': in_review_subs.count(),
        'submissions': in_review_subs,
        'label': 'In Review',
        'icon': 'eye',
        'color': 'info'
    }

    # With Editor - awaiting editorial decision
    with_editor_subs = scoped.filter(status='with_editor').select_related('author', 'journal').order_by('-submitted_at')[:5]
    status_details['with_editor'] = {
        'count': with_editor_subs.count(),
        'submissions': with_editor_subs,
        'label': 'With Editor',
        'icon': 'gavel',
        'color': 'primary'
    }

    # Revision Requested
    revision_subs = scoped.filter(status='revision_requested').select_related('author', 'journal').order_by('-updated_at')[:5]
    status_details['revision_requested'] = {
        'count': revision_subs.count(),
        'submissions': revision_subs,
        'label': 'Revision Requested',
        'icon': 'edit',
        'color': 'danger'
    }

    # Revised - awaiting review
    revised_subs = scoped.filter(status='revised').select_related('author', 'journal').order_by('-updated_at')[:5]
    status_details['revised'] = {
        'count': revised_subs.count(),
        'submissions': revised_subs,
        'label': 'Revised',
        'icon': 'file-alt',
        'color': 'secondary'
    }

    # Approved - ready to publish
    approved_subs = scoped.filter(status='approved').select_related('author', 'journal').order_by('-updated_at')[:5]
    status_details['approved'] = {
        'count': approved_subs.count(),
        'submissions': approved_subs,
        'label': 'Approved',
        'icon': 'check-circle',
        'color': 'success'
    }

    # Published
    published_subs = scoped.filter(status='published').select_related('author', 'journal').order_by('-updated_at')[:5]
    status_details['published'] = {
        'count': published_subs.count(),
        'submissions': published_subs,
        'label': 'Published',
        'icon': 'book-open',
        'color': 'success'
    }

    # Rejected
    rejected_subs = scoped.filter(status='rejected').select_related('author', 'journal').order_by('-updated_at')[:5]
    status_details['rejected'] = {
        'count': rejected_subs.count(),
        'submissions': rejected_subs,
        'label': 'Rejected',
        'icon': 'times-circle',
        'color': 'dark'
    }

    return render(request, 'submissions/admin_submission_list.html', {
        'submissions': submissions,
        'status_filter': status_filter,
        'journal_filter': journal_filter,
        'search_query': search_query,
        'status_choices': Submission.STATUS_CHOICES,
        'journals': permitted_journals,
        'status_counts': {s['status']: s['count'] for s in status_counts},
        'status_details': status_details,
    })


@journal_staff_required(roles=WORKFLOW_ROLES)
def admin_submission_detail(request, pk):
    """Admin view for submission details with actions"""
    submission = get_object_or_404(Submission, pk=pk)

    # Get all related data
    assignments = submission.assignments.all().select_related('assigned_to', 'assigned_by')
    versions = submission.document_versions.all()
    logs = submission.logs.all()[:30]

    # Get chat messages for this submission
    chat_messages = submission.messages.all().select_related('sender', 'recipient')

    # Get eligible users for assignment (reviewers and editors)
    from django.contrib.auth import get_user_model
    User = get_user_model()
    eligible_users = User.objects.filter(
        Q(profile__is_reviewer=True) | Q(profile__is_editor=True)
    ).select_related('profile').distinct().order_by('first_name', 'last_name', 'email')

    # Forms
    assign_form = SubmissionAssignmentForm()
    message_form = SubmissionMessageForm()

    return render(request, 'submissions/admin_submission_detail.html', {
        'submission': submission,
        'assignments': assignments,
        'versions': versions,
        'logs': logs,
        'messages': chat_messages,
        'assign_form': assign_form,
        'message_form': message_form,
        'eligible_users': eligible_users,
        'has_review_copy': submission.has_review_copy,
        'current_round': submission.current_round,
        'review_rounds': submission.review_rounds.all(),
    })


@journal_staff_required(roles=WORKFLOW_ROLES)
def prepare_for_review(request, pk):
    """Chief editor prepares a de-identified review copy before assigning reviewers.

    This is the "downloads and prepares it for Reviewing" step: the editor
    downloads the author's original, strips identifying content, and uploads a
    review-ready copy. Only review copies are ever shown to reviewers, so this
    step is what actually makes the manuscript blind (metadata stripping alone
    can't remove a name typed on the title page). Opens review round 1 if none
    is open yet.
    """
    submission = get_object_or_404(Submission, pk=pk)

    if request.method == 'POST':
        form = ReviewCopyUploadForm(request.POST, request.FILES)
        if form.is_valid():
            version = DocumentVersion.objects.create(
                submission=submission,
                uploaded_by=request.user,
                document=form.cleaned_data['document'],
                notes=form.cleaned_data.get('notes', '') or 'Review-ready copy prepared by editor',
                is_review_copy=True,
            )

            # Open the first round if the review hasn't started yet.
            if submission.current_round is None:
                submission.open_new_round(opened_by=request.user)

            if submission.status == 'pending':
                submission.status = 'preparing'
                submission.save(update_fields=['status'])

            log_submission_action(
                submission, request.user, 'Review copy prepared',
                {'version': version.version_number}
            )
            messages.success(
                request,
                'Review copy uploaded. You can now assign reviewers — they will '
                'download this copy, not the author\'s original.'
            )
            return redirect('admin_submission_detail', pk=pk)
    else:
        form = ReviewCopyUploadForm()

    return render(request, 'submissions/prepare_for_review.html', {
        'form': form,
        'submission': submission,
    })


@journal_staff_required(roles=WORKFLOW_ROLES)
@require_POST
def reopen_review(request, pk):
    """Send a revised submission back out for another round of review.

    After the author revises, the editor opens round N+1. Existing reviewers can
    be re-assigned from the detail page; a fresh review copy of the revised
    manuscript should be prepared first.
    """
    submission = get_object_or_404(Submission, pk=pk)

    if submission.status not in ('revised', 'with_editor', 'in_review'):
        messages.error(request, 'This submission is not in a state that can be sent back to reviewers.')
        return redirect('admin_submission_detail', pk=pk)

    review_round = submission.open_new_round(opened_by=request.user)
    submission.status = 'preparing'
    submission.save(update_fields=['status'])

    log_submission_action(
        submission, request.user, f'Opened review round {review_round.number}',
        {'round': review_round.number}
    )
    messages.success(
        request,
        f'Review round {review_round.number} opened. Prepare a review copy of the '
        f'revised manuscript, then assign reviewers.'
    )
    return redirect('admin_submission_detail', pk=pk)


@journal_staff_required(roles=WORKFLOW_ROLES)
@require_POST
def assign_submission(request, pk):
    """Assign a reviewer or editor to a submission"""
    submission = get_object_or_404(Submission, pk=pk)

    form = SubmissionAssignmentForm(request.POST)
    if form.is_valid():
        # A reviewer must never receive the author's original — require a
        # prepared review copy before a reviewer can be assigned.
        if form.cleaned_data.get('role') == 'reviewer' and not submission.has_review_copy:
            messages.error(
                request,
                'Prepare a review copy first — reviewers must not receive the '
                'author\'s original document.'
            )
            return redirect('admin_submission_detail', pk=pk)

        assignment = form.save(commit=False)
        assignment.submission = submission
        assignment.assigned_by = request.user
        # Attach to the current round (opening round 1 if needed).
        assignment.review_round = submission.current_round or submission.open_new_round(opened_by=request.user)
        assignment.save()

        # Update submission status based on assignment
        if assignment.role == 'reviewer' and submission.status in ('pending', 'preparing'):
            submission.status = 'in_review'
            submission.save()
        elif assignment.role == 'editor':
            submission.status = 'with_editor'
            submission.save()

        # Log the action
        log_submission_action(
            submission, request.user, f'Assigned to {assignment.get_role_display()}',
            {
                'assigned_to': assignment.assigned_to.email,
                'role': assignment.role
            }
        )

        # TODO: Send email notification to assignee

        messages.success(request, f'{assignment.get_role_display()} has been assigned successfully.')
    else:
        messages.error(request, 'Error assigning submission. Please try again.')

    return redirect('admin_submission_detail', pk=pk)


@journal_staff_required(roles=WORKFLOW_ROLES)
def request_revision(request, pk):
    """Request revisions from the author"""
    submission = get_object_or_404(Submission, pk=pk)

    if request.method == 'POST':
        form = RevisionRequestForm(request.POST)
        if form.is_valid():
            notes = form.cleaned_data['notes']

            submission.status = 'revision_requested'
            submission.save()

            # Log the action
            log_submission_action(
                submission, request.user, 'Revision requested',
                {'notes': notes}
            )

            # Send email to author
            # TODO: Implement email notification

            messages.success(request, 'Revision request has been sent to the author.')
            return redirect('admin_submission_detail', pk=pk)
    else:
        form = RevisionRequestForm()

    # Get completed assignments for context
    completed_assignments = submission.assignments.filter(status='completed').select_related('assigned_to')

    return render(request, 'submissions/request_revision.html', {
        'form': form,
        'submission': submission,
        'completed_assignments': completed_assignments,
    })


@journal_staff_required(roles=WORKFLOW_ROLES)
def upload_final_document(request, pk):
    """Upload the final approved document for extraction"""
    submission = get_object_or_404(Submission, pk=pk)

    if request.method == 'POST':
        form = FinalDocumentUploadForm(request.POST, request.FILES)
        if form.is_valid():
            document = form.cleaned_data['document']
            notes = form.cleaned_data.get('notes', '')

            # Create final document version
            version = DocumentVersion.objects.create(
                submission=submission,
                uploaded_by=request.user,
                document=document,
                notes=notes,
                is_final=True
            )

            # Extract content from document
            document.seek(0)  # Reset file pointer
            extracted = extract_document_content(document)

            # Update submission status
            submission.status = 'approved'
            submission.save()

            # Log the action
            log_submission_action(
                submission, request.user, 'Final document uploaded',
                {'version': version.version_number}
            )

            # Store extracted content in session for review
            request.session['extracted_content'] = extracted
            request.session['final_version_id'] = version.id

            messages.success(request, 'Document uploaded and content extracted. Please review before publishing.')
            return redirect('preview_extracted_content', pk=pk)
    else:
        form = FinalDocumentUploadForm()

    return render(request, 'submissions/upload_final.html', {
        'form': form,
        'submission': submission
    })


@journal_staff_required(roles=WORKFLOW_ROLES)
def preview_extracted_content(request, pk):
    """Preview extracted content before publishing"""
    submission = get_object_or_404(Submission, pk=pk)

    # Get extracted content from session
    extracted = request.session.get('extracted_content', {})

    if not extracted:
        messages.warning(request, 'No extracted content found. Please upload the final document first.')
        return redirect('upload_final_document', pk=pk)

    # Pre-fill the publish form with extracted content
    initial_data = {
        'title': extracted.get('title') or submission.title,
        'abstract': extracted.get('abstract', ''),
        'keywords': extracted.get('keywords', ''),
        'content': extracted.get('content', ''),
        'extracted_citations': extracted.get('citations', ''),
    }

    form = PublishArticleForm(initial=initial_data)

    # Get categories for the submission's journal
    from .models import ArticleCategory
    categories = ArticleCategory.objects.filter(journal=submission.journal).order_by('name')

    return render(request, 'submissions/preview_extracted.html', {
        'form': form,
        'submission': submission,
        'extracted': extracted,
        'categories': categories,
    })


@journal_staff_required(roles=DECISION_ROLES)
@require_POST
def publish_submission(request, pk):
    """Publish the submission as an article"""
    submission = get_object_or_404(Submission, pk=pk)

    # Publication is gated on the fee: if the journal charges and the fee isn't
    # settled, hold here and notify the author to pay rather than publishing.
    if submission.requires_payment:
        from .payment_views import ensure_payment_requested
        ensure_payment_requested(submission, request)
        messages.warning(
            request,
            'This journal charges a publication fee. The author has been notified '
            'to pay; you can publish once the payment clears (or waive the fee).'
        )
        return redirect('admin_submission_detail', pk=pk)

    # Handle new category creation
    category_value = request.POST.get('category', '')
    new_category_name = request.POST.get('new_category', '').strip()

    if category_value == '__new__' and new_category_name:
        from .models import ArticleCategory
        # Create new category for this journal
        category, created = ArticleCategory.objects.get_or_create(
            journal=submission.journal,
            name=new_category_name,
            defaults={'description': ''}
        )
        # Update POST data to use the new category ID
        post_data = request.POST.copy()
        post_data['category'] = category.id
        form = PublishArticleForm(post_data)
    else:
        form = PublishArticleForm(request.POST)

    if form.is_valid():
        # Create the article
        article = form.save(commit=False)
        article.author = submission.author
        article.journal = submission.journal
        article.status = 'published'
        article.published_at = timezone.now()

        # Get the final document version
        final_version_id = request.session.get('final_version_id')
        if final_version_id:
            try:
                final_version = DocumentVersion.objects.get(id=final_version_id)
                article.final_document = final_version.document
            except DocumentVersion.DoesNotExist:
                pass

        article.save()

        # Link submission to article
        submission.published_article = article
        submission.status = 'published'
        submission.save()

        # Log the action
        log_submission_action(
            submission, request.user, 'Article published',
            {'article_id': article.id}
        )

        # Clear session data
        if 'extracted_content' in request.session:
            del request.session['extracted_content']
        if 'final_version_id' in request.session:
            del request.session['final_version_id']

        messages.success(request, f'Article "{article.title}" has been published successfully!')
        return redirect('article_detail', pk=article.pk)
    else:
        messages.error(request, 'Error publishing article. Please check the form.')
        return redirect('preview_extracted_content', pk=pk)


@journal_staff_required(roles=DECISION_ROLES)
@require_POST
def reject_submission(request, pk):
    """Reject a submission"""
    submission = get_object_or_404(Submission, pk=pk)

    reason = request.POST.get('reason', '')

    submission.status = 'rejected'
    submission.save()

    # Log the action
    log_submission_action(
        submission, request.user, 'Submission rejected',
        {'reason': reason}
    )

    # Notify the author.
    try:
        context = {
            'submission': submission,
            'author': submission.author,
            'reason': reason,
            'site_name': 'University of Jos Journal',
        }
        html_message = render_to_string('emails/submission_rejected.html', context)
        email = EmailMultiAlternatives(
            subject=f'Decision on your submission — {submission.title or submission.anonymized_identifier}',
            body=strip_tags(html_message),
            from_email=get_from_email(),
            to=[submission.author.email],
        )
        email.attach_alternative(html_message, "text/html")
        email.send()
    except Exception:
        logger.error('Failed to send rejection email for submission %s', submission.pk, exc_info=True)

    messages.success(request, 'Submission has been rejected and the author notified.')
    return redirect('admin_submission_detail', pk=pk)


@journal_staff_required(roles=DECISION_ROLES)
def approve_submission(request, pk):
    """Approve a submission after reviewer completion"""
    submission = get_object_or_404(Submission, pk=pk)

    # Validate that submission can be approved
    if submission.status not in ['in_review', 'with_editor', 'revised']:
        messages.error(request, 'This submission cannot be approved in its current state.')
        return redirect('admin_submission_detail', pk=pk)

    if request.method == 'POST':
        # Update submission status to approved
        submission.status = 'approved'
        submission.save()

        # Log the action
        log_submission_action(
            submission, request.user, 'Submission approved',
            {'previous_status': submission.status}
        )

        # Send approval notification email to author
        try:
            subject = f'Your Submission Has Been Approved - {submission.title}'
            context = {
                'submission': submission,
                'author': submission.author,
                'site_name': 'University of Jos Journal',
            }
            html_message = render_to_string('emails/submission_approved.html', context)
            plain_message = strip_tags(html_message)

            email = EmailMultiAlternatives(
                subject=subject,
                body=plain_message,
                from_email=get_from_email(),
                to=[submission.author.email]
            )
            email.attach_alternative(html_message, "text/html")
            email.send()
        except Exception as e:
            # Log error but don't fail the approval
            pass

        messages.success(request, f'Submission "{submission.title}" has been approved. You can now upload the final document for publishing.')
        return redirect('upload_final_document', pk=pk)

    # GET request - show confirmation page
    # Get completed assignments with feedback
    completed_assignments = submission.assignments.filter(status='completed').select_related('assigned_to')

    return render(request, 'submissions/approve_submission.html', {
        'submission': submission,
        'completed_assignments': completed_assignments,
    })


@journal_staff_required(roles=WORKFLOW_ROLES)
def share_with_author(request, pk):
    """Share reviewed document and feedback with author"""
    submission = get_object_or_404(Submission, pk=pk)

    # Get completed assignments with feedback
    completed_assignments = submission.assignments.filter(status='completed').select_related('assigned_to')

    # Get the latest document version
    latest_version = submission.document_versions.order_by('-version_number').first()

    # Get amended documents from reviewers
    amended_documents = []
    for assignment in completed_assignments:
        if assignment.amended_document:
            amended_documents.append({
                'reviewer': assignment.assigned_to,
                'document': assignment.amended_document,
                'recommendation': assignment.get_recommendation_display() if assignment.recommendation else 'N/A'
            })

    if request.method == 'POST':
        # Send email to author with document links and feedback summary
        try:
            subject = f'Review Feedback for Your Submission - {submission.title}'

            # Build feedback summary
            feedback_summary = []
            for assignment in completed_assignments:
                feedback_summary.append({
                    'reviewer': assignment.assigned_to.get_full_name() or assignment.assigned_to.email,
                    'recommendation': assignment.get_recommendation_display() if assignment.recommendation else 'N/A',
                    'feedback': assignment.feedback or 'No written feedback provided.',
                    'has_amended_doc': bool(assignment.amended_document)
                })

            context = {
                'submission': submission,
                'author': submission.author,
                'feedback_summary': feedback_summary,
                'submission_url': request.build_absolute_uri(reverse('submission_detail', args=[submission.pk])),
                'site_name': 'University of Jos Journal',
            }

            html_message = render_to_string('emails/share_with_author.html', context)
            plain_message = strip_tags(html_message)

            email = EmailMultiAlternatives(
                subject=subject,
                body=plain_message,
                from_email=get_from_email(),
                to=[submission.author.email]
            )
            email.attach_alternative(html_message, "text/html")
            email.send()

            # Log the action
            log_submission_action(
                submission, request.user, 'Feedback shared with author',
                {'reviewers_count': completed_assignments.count()}
            )

            messages.success(request, f'Review feedback has been shared with {submission.author.email}.')
        except Exception as e:
            messages.error(request, f'Error sending email: {str(e)}')

        return redirect('admin_dashboard')

    return render(request, 'submissions/share_with_author.html', {
        'submission': submission,
        'completed_assignments': completed_assignments,
        'latest_version': latest_version,
        'amended_documents': amended_documents,
    })


# ============================================================================
# Reviewer/Editor Views
# ============================================================================

@login_required
def my_assignments(request):
    """View assignments for the current reviewer/editor"""
    profile = request.user.profile

    if not (profile.is_reviewer or profile.is_editor):
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('dashboard')

    # Get active assignments
    assignments = Assignment.objects.filter(
        assigned_to=request.user,
        status='active'
    ).select_related('submission', 'submission__author', 'submission__journal')

    # Get completed assignments
    completed = Assignment.objects.filter(
        assigned_to=request.user,
        status='completed'
    ).select_related('submission')[:10]

    return render(request, 'submissions/my_assignments.html', {
        'assignments': assignments,
        'completed': completed
    })


@login_required
def work_on_submission(request, pk):
    """Work on an assigned submission (for reviewers/editors)"""
    submission = get_object_or_404(Submission, pk=pk)

    # Check if user is assigned to this submission
    assignment = get_object_or_404(
        Assignment,
        submission=submission,
        assigned_to=request.user,
        status='active'
    )

    # Get chat messages
    chat_messages = submission.messages.filter(
        Q(sender=request.user) |
        Q(recipient=request.user) |
        Q(recipient__isnull=True)  # Group messages
    ).select_related('sender', 'recipient')

    # Reviewers only see review copies, never the author's original upload.
    versions = submission.document_versions.filter(is_review_copy=True)

    # Forms
    feedback_form = AssignmentFeedbackForm(instance=assignment)
    message_form = SubmissionMessageForm()

    if request.method == 'POST':
        if 'submit_feedback' in request.POST:
            feedback_form = AssignmentFeedbackForm(request.POST, request.FILES, instance=assignment)
            if feedback_form.is_valid():
                assignment = feedback_form.save(commit=False)
                assignment.status = 'completed'
                assignment.completed_at = timezone.now()
                assignment.save()

                # Log the action
                log_data = {
                    'recommendation': assignment.recommendation,
                    'feedback_length': len(assignment.feedback)
                }
                if assignment.amended_document:
                    log_data['amended_document'] = assignment.amended_document.name

                log_submission_action(
                    submission, request.user, f'{assignment.get_role_display()} feedback submitted',
                    log_data
                )

                messages.success(request, 'Your feedback has been submitted successfully.')
                return redirect('my_assignments')

    return render(request, 'submissions/work_on_submission.html', {
        'submission': submission,
        'assignment': assignment,
        'messages': chat_messages,
        'versions': versions,
        'feedback_form': feedback_form,
        'message_form': message_form
    })


# ============================================================================
# Chat/Messaging API
# ============================================================================

@login_required
@require_POST
def send_message(request, submission_id):
    """Send a chat message"""
    submission = get_object_or_404(Submission, pk=submission_id)

    # Check permission
    if not has_journal_role(request.user, submission.journal, roles=WORKFLOW_ROLES):
        if submission.author != request.user:
            if not submission.assignments.filter(assigned_to=request.user).exists():
                return JsonResponse({'error': 'Permission denied'}, status=403)

    form = SubmissionMessageForm(request.POST, request.FILES)
    if form.is_valid():
        message = form.save(commit=False)
        message.submission = submission
        message.sender = request.user
        message.save()

        return JsonResponse({
            'success': True,
            'message': {
                'id': message.id,
                'content': message.content,
                'sender': message.sender.get_full_name() or message.sender.email,
                'created_at': message.created_at.strftime('%Y-%m-%d %H:%M'),
                'attachment': message.attachment.url if message.attachment else None
            }
        })

    return JsonResponse({'error': 'Invalid form data'}, status=400)


@login_required
@require_GET
def get_messages(request, submission_id):
    """Get chat messages for a submission"""
    submission = get_object_or_404(Submission, pk=submission_id)

    # Check permission
    if not has_journal_role(request.user, submission.journal, roles=WORKFLOW_ROLES):
        if submission.author != request.user:
            if not submission.assignments.filter(assigned_to=request.user).exists():
                return JsonResponse({'error': 'Permission denied'}, status=403)

    # Get messages
    messages_qs = submission.messages.filter(
        Q(sender=request.user) |
        Q(recipient=request.user) |
        Q(recipient__isnull=True)  # Group messages
    ).select_related('sender', 'recipient').order_by('created_at')

    # Mark messages as read
    messages_qs.filter(recipient=request.user, is_read=False).update(is_read=True)

    messages_data = []
    for msg in messages_qs:
        messages_data.append({
            'id': msg.id,
            'content': msg.content,
            'sender': msg.sender.get_full_name() or msg.sender.email,
            'sender_id': msg.sender.id,
            'is_mine': msg.sender == request.user,
            'created_at': msg.created_at.strftime('%Y-%m-%d %H:%M'),
            'attachment': msg.attachment.url if msg.attachment else None
        })

    return JsonResponse({'messages': messages_data})


@login_required
@require_GET
def unread_message_count(request):
    """Get count of unread messages for the current user"""
    count = SubmissionMessage.objects.filter(
        recipient=request.user,
        is_read=False
    ).count()

    return JsonResponse({'count': count})


# ============================================================================
# Document Download
# ============================================================================

@login_required
def download_document(request, version_id):
    """Download a document version"""
    from .utils import sanitize_document_metadata, get_sanitized_filename

    version = get_object_or_404(DocumentVersion, pk=version_id)
    submission = version.submission

    # Check permission and determine if blinded review
    is_blinded = False
    assignment = None

    if not has_journal_role(request.user, submission.journal, roles=WORKFLOW_ROLES):
        if submission.author != request.user:
            # Check if user has an assignment for this submission
            assignment = submission.assignments.filter(assigned_to=request.user).first()
            if not assignment:
                messages.error(request, 'You do not have permission to download this document.')
                return redirect('dashboard')
            # Reviewers may only download review copies — never the author's
            # original upload, which can carry identifying content in the body.
            if not version.is_review_copy:
                messages.error(request, 'This document is not available for review.')
                return redirect('work_on_submission', pk=submission.pk)
            # Check if this is a blinded review
            is_blinded = assignment.blinded
        else:
            # Author downloading their own document - not blinded
            is_blinded = False
    else:
        # Admin can see everything - not blinded
        is_blinded = False

    # Get the document
    document_path = version.document.path
    filename = version.document.name.split("/")[-1]

    # If blinded review, sanitize the document
    if is_blinded:
        sanitized_doc = sanitize_document_metadata(document_path)
        if sanitized_doc:
            # Use sanitized document
            sanitized_filename = get_sanitized_filename(filename, submission.anonymized_identifier)
            response = HttpResponse(
                sanitized_doc.getvalue(),
                content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
            )
            response['Content-Disposition'] = f'attachment; filename="{sanitized_filename}"'
            return response
        # If sanitization failed, fall back to original (logged in utils.py)

    # Serve the original file (for author, admin, or if sanitization failed)
    response = HttpResponse(version.document, content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


# ============================================================================
# Guest Reviewer Email Helper Functions
# ============================================================================

def send_guest_invitation_email(guest_reviewer, request):
    """Send invitation email to guest reviewer"""
    site_name = "University of Jos Journal System"
    review_url = request.build_absolute_uri(
        reverse('guest_review_access', kwargs={'token': guest_reviewer.invitation_token})
    )

    context = {
        'guest_reviewer': guest_reviewer,
        'site_name': site_name,
        'review_url': review_url,
        'expiration_date': guest_reviewer.token_expires_at,
        'contact_email': settings.DEFAULT_FROM_EMAIL,
    }

    html_content = render_to_string('emails/guest_reviewer_invitation.html', context)
    text_content = strip_tags(html_content)

    email = EmailMultiAlternatives(
        subject=f'Invitation to Review for {site_name}',
        body=text_content,
        from_email=get_from_email(),
        to=[guest_reviewer.email]
    )
    email.attach_alternative(html_content, "text/html")
    email.send()


def send_guest_assignment_email(assignment, request):
    """Send assignment notification to guest reviewer"""
    site_name = "University of Jos Journal System"
    review_url = request.build_absolute_uri(
        reverse('guest_work_on_submission', kwargs={
            'submission_id': assignment.submission.pk,
            'access_token': assignment.access_token
        })
    )

    context = {
        'guest_reviewer': assignment.guest_reviewer,
        'submission': assignment.submission,
        'journal': assignment.submission.journal,
        'blinded': assignment.blinded,
        'notes': assignment.notes,
        'site_name': site_name,
        'review_url': review_url,
        'contact_email': settings.DEFAULT_FROM_EMAIL,
    }

    html_content = render_to_string('emails/guest_assignment_notification.html', context)
    text_content = strip_tags(html_content)

    email = EmailMultiAlternatives(
        subject=f'New Review Assignment - {assignment.submission.journal.name}',
        body=text_content,
        from_email=get_from_email(),
        to=[assignment.guest_reviewer.email]
    )
    email.attach_alternative(html_content, "text/html")
    email.send()


def send_guest_feedback_confirmation(assignment, request):
    """Send confirmation to guest after submission"""
    site_name = "University of Jos Journal System"

    context = {
        'guest_reviewer': assignment.guest_reviewer,
        'submission': assignment.submission,
        'journal': assignment.submission.journal,
        'blinded': assignment.blinded,
        'recommendation': assignment.get_recommendation_display(),
        'submitted_at': assignment.completed_at,
        'site_name': site_name,
        'contact_email': settings.DEFAULT_FROM_EMAIL,
    }

    html_content = render_to_string('emails/guest_feedback_confirmation.html', context)
    text_content = strip_tags(html_content)

    email = EmailMultiAlternatives(
        subject=f'Review Submitted - {assignment.submission.anonymized_identifier}',
        body=text_content,
        from_email=get_from_email(),
        to=[assignment.guest_reviewer.email]
    )
    email.attach_alternative(html_content, "text/html")
    email.send()


def send_admin_feedback_notification(assignment, request):
    """Notify admin of new guest feedback"""
    site_name = "University of Jos Journal System"
    admin_url = request.build_absolute_uri(
        reverse('admin_submission_detail', kwargs={'pk': assignment.submission.pk})
    )

    context = {
        'guest_reviewer': assignment.guest_reviewer,
        'submission': assignment.submission,
        'journal': assignment.submission.journal,
        'recommendation': assignment.recommendation,
        'submitted_at': assignment.completed_at,
        'amended_document': assignment.amended_document,
        'site_name': site_name,
        'admin_url': admin_url,
    }

    html_content = render_to_string('emails/admin_guest_feedback_notification.html', context)
    text_content = strip_tags(html_content)

    # Notify site staff plus this journal's editorial team — a chief editor who
    # isn't site staff still needs to hear that their reviewer has reported back.
    journal = assignment.submission.journal
    staff_emails = set(
        CustomUser.objects.filter(is_staff=True, is_active=True)
        .values_list('email', flat=True)
    )
    staff_emails.update(
        CustomUser.objects.filter(
            is_active=True,
            journal_roles__journal=journal,
            journal_roles__role__in=WORKFLOW_ROLES,
        ).values_list('email', flat=True)
    )

    email = EmailMultiAlternatives(
        subject=f'Guest Review Feedback Received - {assignment.submission.anonymized_identifier}',
        body=text_content,
        from_email=get_from_email(),
        to=list(staff_emails)
    )
    email.attach_alternative(html_content, "text/html")
    email.send()


# ============================================================================
# Guest Reviewer Management Views
# ============================================================================

@journal_staff_required(roles=WORKFLOW_ROLES, lookup='none')
def add_guest_reviewer(request):
    """Add a single guest reviewer and send invitation"""
    if request.method == 'POST':
        form = GuestReviewerForm(request.POST)
        if form.is_valid():
            guest_reviewer = form.save(commit=False)
            guest_reviewer.created_by = request.user
            guest_reviewer.save()

            # Send invitation email
            try:
                send_guest_invitation_email(guest_reviewer, request)
                messages.success(request, f'Guest reviewer {guest_reviewer.get_full_name()} added and invitation sent.')
            except Exception as e:
                messages.warning(request, f'Guest reviewer added but email failed: {str(e)}')

            return redirect('manage_guest_reviewers')
    else:
        form = GuestReviewerForm()

    context = {
        'form': form,
        'title': 'Add Guest Reviewer'
    }
    return render(request, 'submissions/admin_add_guest_reviewer.html', context)


@journal_staff_required(roles=WORKFLOW_ROLES, lookup='none')
def bulk_add_guest_reviewers(request):
    """Add multiple guest reviewers from CSV"""
    if request.method == 'POST':
        form = BulkGuestReviewerForm(request.POST)
        if form.is_valid():
            reviewers_data = form.cleaned_data['reviewer_list']
            created_count = 0
            failed = []

            for reviewer_data in reviewers_data:
                try:
                    guest_reviewer = GuestReviewer.objects.create(
                        email=reviewer_data['email'],
                        first_name=reviewer_data['first_name'],
                        last_name=reviewer_data['last_name'],
                        affiliation=reviewer_data['affiliation'],
                        created_by=request.user
                    )
                    # Send invitation email
                    send_guest_invitation_email(guest_reviewer, request)
                    created_count += 1
                except Exception as e:
                    failed.append(f"{reviewer_data['email']}: {str(e)}")

            if created_count > 0:
                messages.success(request, f'Successfully added {created_count} guest reviewer(s).')
            if failed:
                messages.warning(request, f'Failed to add: {", ".join(failed)}')

            return redirect('manage_guest_reviewers')
    else:
        form = BulkGuestReviewerForm()

    context = {
        'form': form,
        'title': 'Bulk Add Guest Reviewers'
    }
    return render(request, 'submissions/admin_bulk_add_guests.html', context)


@journal_staff_required(roles=WORKFLOW_ROLES, lookup='none')
def manage_guest_reviewers(request):
    """List and manage all guest reviewers"""
    guest_reviewers = GuestReviewer.objects.all().order_by('-created_at')

    # Search functionality
    search_query = request.GET.get('search', '')
    if search_query:
        guest_reviewers = guest_reviewers.filter(
            Q(email__icontains=search_query) |
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(affiliation__icontains=search_query)
        )

    # Filter by active status
    status_filter = request.GET.get('status', 'all')
    if status_filter == 'active':
        guest_reviewers = guest_reviewers.filter(is_active=True)
    elif status_filter == 'inactive':
        guest_reviewers = guest_reviewers.filter(is_active=False)

    context = {
        'guest_reviewers': guest_reviewers,
        'search_query': search_query,
        'status_filter': status_filter,
        'title': 'Manage Guest Reviewers'
    }
    return render(request, 'submissions/admin_manage_guests.html', context)


@journal_staff_required(roles=WORKFLOW_ROLES, lookup='none')
def edit_guest_reviewer(request, pk):
    """Edit guest reviewer details"""
    guest_reviewer = get_object_or_404(GuestReviewer, pk=pk)

    if request.method == 'POST':
        form = GuestReviewerForm(request.POST, instance=guest_reviewer)
        if form.is_valid():
            form.save()
            messages.success(request, f'Guest reviewer {guest_reviewer.get_full_name()} updated successfully.')
            return redirect('manage_guest_reviewers')
    else:
        form = GuestReviewerForm(instance=guest_reviewer)

    context = {
        'form': form,
        'guest_reviewer': guest_reviewer,
        'title': 'Edit Guest Reviewer'
    }
    return render(request, 'submissions/admin_add_guest_reviewer.html', context)


@journal_staff_required(roles=WORKFLOW_ROLES, lookup='none')
def resend_guest_invitation(request, pk):
    """Regenerate token and resend invitation"""
    guest_reviewer = get_object_or_404(GuestReviewer, pk=pk)

    # Regenerate token
    guest_reviewer.regenerate_token()

    # Send invitation email
    try:
        send_guest_invitation_email(guest_reviewer, request)
        messages.success(request, f'Invitation resent to {guest_reviewer.get_full_name()}.')
    except Exception as e:
        messages.error(request, f'Failed to send invitation: {str(e)}')

    return redirect('manage_guest_reviewers')


# ============================================================================
# Guest Review Access Views (No Login Required)
# ============================================================================

def guest_review_access(request, token):
    """Landing page for guest reviewers using invitation token"""
    guest_reviewer = get_object_or_404(GuestReviewer, invitation_token=token)

    # Check if token is valid
    if not guest_reviewer.is_token_valid():
        context = {
            'error': 'Your invitation has expired. Please contact the editorial office.',
            'guest_reviewer': guest_reviewer,
        }
        return render(request, 'submissions/guest_access_error.html', context)

    # Get all active assignments for this guest
    assignments = Assignment.objects.filter(
        guest_reviewer=guest_reviewer,
        status='active'
    ).select_related('submission', 'submission__journal')

    context = {
        'guest_reviewer': guest_reviewer,
        'assignments': assignments,
        'token': token,
    }
    return render(request, 'submissions/guest_review_access.html', context)


def guest_work_on_submission(request, submission_id, access_token):
    """Guest reviewer interface for reviewing submission"""
    # Get assignment by access token
    assignment = get_object_or_404(
        Assignment,
        submission_id=submission_id,
        access_token=access_token,
        guest_reviewer__isnull=False
    )

    # Check if assignment is still active
    if assignment.status != 'active':
        messages.info(request, 'This review has already been submitted.')
        return redirect('guest_review_access', token=assignment.guest_reviewer.invitation_token)

    submission = assignment.submission

    # Guests only see review copies, never the author's original upload.
    versions = submission.document_versions.filter(
        is_review_copy=True
    ).order_by('-version_number')

    # Handle feedback submission
    if request.method == 'POST' and 'submit_feedback' in request.POST:
        form = AssignmentFeedbackForm(request.POST, request.FILES, instance=assignment)
        if form.is_valid():
            assignment = form.save(commit=False)
            assignment.status = 'completed'
            assignment.completed_at = timezone.now()
            assignment.save()

            # Create log entry
            SubmissionLog.objects.create(
                submission=submission,
                user=None,
                action=f'Guest reviewer {assignment.guest_reviewer.get_full_name()} submitted feedback',
                details={'recommendation': assignment.recommendation}
            )

            # Send confirmation email to guest
            try:
                send_guest_feedback_confirmation(assignment, request)
            except Exception as e:
                print(f"Failed to send guest confirmation email: {e}")

            # Send notification to admin
            try:
                send_admin_feedback_notification(assignment, request)
            except Exception as e:
                print(f"Failed to send admin notification email: {e}")

            return redirect('guest_feedback_submitted',
                          submission_id=submission.pk,
                          access_token=access_token)
    else:
        form = AssignmentFeedbackForm(instance=assignment)

    context = {
        'assignment': assignment,
        'submission': submission,
        'versions': versions,
        'feedback_form': form,
        'guest_reviewer': assignment.guest_reviewer,
    }
    return render(request, 'submissions/guest_work_on_submission.html', context)


def guest_feedback_submitted(request, submission_id, access_token):
    """Thank you page after guest submits feedback"""
    assignment = get_object_or_404(
        Assignment,
        submission_id=submission_id,
        access_token=access_token,
        guest_reviewer__isnull=False,
        status='completed'
    )

    context = {
        'assignment': assignment,
        'submission': assignment.submission,
        'guest_reviewer': assignment.guest_reviewer,
    }
    return render(request, 'submissions/guest_feedback_submitted.html', context)


def guest_download_document(request, version_id, access_token):
    """
    Guest reviewer document download - no login required.
    Validates access via assignment token.
    """
    from .utils import sanitize_document_metadata, get_sanitized_filename

    version = get_object_or_404(DocumentVersion, pk=version_id)
    submission = version.submission

    # Validate guest has access to this submission
    assignment = get_object_or_404(
        Assignment,
        submission=submission,
        access_token=access_token,
        guest_reviewer__isnull=False
    )

    # Verify guest reviewer token is still valid
    if not assignment.guest_reviewer.is_token_valid():
        messages.error(request, 'Your access has expired. Please contact the editorial office.')
        return redirect('guest_review_access', token=assignment.guest_reviewer.invitation_token)

    # Guests, like logged-in reviewers, only ever receive review copies.
    if not version.is_review_copy:
        messages.error(request, 'This document is not available for review.')
        return redirect('guest_work_on_submission',
                        submission_id=submission.pk, access_token=access_token)

    # Get the document
    document_path = version.document.path
    filename = version.document.name.split("/")[-1]

    # Always sanitize for guest reviewers if blinded
    if assignment.blinded:
        sanitized_doc = sanitize_document_metadata(document_path)
        if sanitized_doc:
            # Use sanitized document
            sanitized_filename = get_sanitized_filename(filename, submission.anonymized_identifier)
            response = HttpResponse(
                sanitized_doc.getvalue(),
                content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
            )
            response['Content-Disposition'] = f'attachment; filename="{sanitized_filename}"'
            return response

    # Serve the original file if not blinded or sanitization failed
    response = HttpResponse(version.document, content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


# ============================================================================
# Journal Team Management (per-journal roles)
# ============================================================================

@journal_staff_required(roles=CONTENT_ROLES, lookup='journal')
def journal_team(request, pk):
    """Show and grant editorial roles for one journal."""
    journal = get_object_or_404(Journal, pk=pk)

    if request.method == 'POST':
        form = JournalRoleForm(request.POST, journal=journal)
        if form.is_valid():
            role = form.save(granted_by=request.user)
            messages.success(
                request,
                f'{role.user.get_full_name() or role.user.email} is now '
                f'{role.get_role_display()} of {journal.name}.'
            )
            return redirect('journal_team', pk=journal.pk)
    else:
        form = JournalRoleForm(journal=journal)

    roles = (
        journal.roles
        .select_related('user', 'granted_by')
        .order_by('role', 'user__email')
    )

    return render(request, 'submissions/journal_team.html', {
        'journal': journal,
        'roles': roles,
        'form': form,
        'site_admins': CustomUser.objects.filter(
            is_staff=True, is_active=True
        ).order_by('email'),
    })


@journal_staff_required(roles=CONTENT_ROLES, lookup='journal')
@require_POST
def journal_role_revoke(request, pk, role_id):
    """Revoke one editorial role."""
    journal = get_object_or_404(Journal, pk=pk)
    role = get_object_or_404(JournalRole, pk=role_id, journal=journal)

    # Don't let the last chief editor remove themselves and lock the journal's
    # team management out (only chief editors and site staff can manage it).
    # Site staff can always recover it, but the dead end is worth blocking.
    if role.user == request.user and role.role == JournalRole.ROLE_CHIEF_EDITOR:
        remaining = JournalRole.objects.filter(
            journal=journal, role=JournalRole.ROLE_CHIEF_EDITOR
        ).exclude(pk=role.pk).exists()
        if not remaining:
            messages.error(
                request,
                'You are the only Chief Editor. Grant the role to someone else '
                'before removing your own.'
            )
            return redirect('journal_team', pk=journal.pk)

    label = f'{role.user.email} ({role.get_role_display()})'
    role.delete()
    messages.success(request, f'Removed {label} from {journal.name}.')
    return redirect('journal_team', pk=journal.pk)
