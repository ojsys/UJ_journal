"""
Journal content management: review rubrics and the submission checklist.

These are the Chief Editor's tools for one journal (rubrics and checklist are
per-journal), so every view here is gated with ``@journal_staff_required`` on
``CONTENT_ROLES``. Site staff pass through as always.
"""
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required

from .models import Journal, Rubric, ChecklistItem, JournalFee
from .forms import RubricForm, ChecklistItemForm, JournalFeeForm
from .permissions import journal_staff_required, journals_for, CONTENT_ROLES


# ---------------------------------------------------------------------------
# Management hub
# ---------------------------------------------------------------------------

@login_required
def journal_manage_list(request):
    """Journals the current user may manage — entry point to team/rubrics/checklist."""
    journals = (
        journals_for(request.user, roles=CONTENT_ROLES)
        .select_related('department')
        .prefetch_related('rubrics', 'checklist_items')
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
