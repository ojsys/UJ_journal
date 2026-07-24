"""
Publication-fee payments via Paystack.

Payment gates *publication*, never submission: an accepted article is held at
``awaiting_payment`` until the fee is paid or an editor waives it. The webhook
is the authoritative confirmation (a user who closes the tab must still be
credited); the browser callback is a convenience that verifies server-side.
"""
import json
import logging
import uuid

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.mail import EmailMultiAlternatives
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.html import strip_tags
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from . import paystack
from .models import Payment, Submission
from .permissions import DECISION_ROLES, has_journal_role, journal_staff_required
from .utils import get_from_email

logger = logging.getLogger('journalapp')


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _new_reference():
    return f"UJ-{uuid.uuid4().hex[:20]}"


def _pending_payment(submission):
    """The current unresolved payment for a submission, if any."""
    return submission.payments.filter(status='pending').first()


def ensure_payment_requested(submission, request):
    """Move a submission to awaiting_payment, create a pending Payment if needed,
    and email the author a pay link. Idempotent — reuses an open pending row."""
    fee = submission.active_fee
    if fee is None:
        return None

    payment = _pending_payment(submission)
    if payment is None:
        payment = Payment.objects.create(
            submission=submission,
            author=submission.author,
            amount=fee.amount,
            currency=fee.currency,
            reference=_new_reference(),
        )

    if submission.status != 'awaiting_payment':
        submission.status = 'awaiting_payment'
        submission.save(update_fields=['status'])

    try:
        pay_url = request.build_absolute_uri(reverse('submission_detail', args=[submission.pk]))
        html = render_to_string('emails/payment_request.html', {
            'submission': submission,
            'author': submission.author,
            'amount': fee.amount,
            'currency': fee.currency,
            'pay_url': pay_url,
        })
        email = EmailMultiAlternatives(
            subject=f'Publication fee for your accepted article — {submission.title or submission.anonymized_identifier}',
            body=strip_tags(html), from_email=get_from_email(),
            to=[submission.author.email],
        )
        email.attach_alternative(html, "text/html")
        email.send()
    except Exception:
        logger.error('Payment request email failed for submission %s', submission.pk, exc_info=True)

    return payment


def _mark_success(payment, paystack_data):
    """Idempotently mark a payment successful and clear the submission for
    publication (back to 'approved' so the editor can complete publishing)."""
    if payment.status == 'success':
        return
    payment.status = 'success'
    payment.paid_at = timezone.now()
    payment.paystack_reference = str(paystack_data.get('reference', payment.reference))
    payment.raw_response = paystack_data
    payment.save()

    submission = payment.submission
    if submission.status == 'awaiting_payment':
        submission.status = 'approved'
        submission.save(update_fields=['status'])

    from .submission_views import log_submission_action
    log_submission_action(
        submission, None, 'Publication fee paid',
        {'reference': payment.reference, 'amount': str(payment.amount)}
    )


# ---------------------------------------------------------------------------
# Editor: request payment / waive
# ---------------------------------------------------------------------------

@journal_staff_required(roles=DECISION_ROLES)
@require_POST
def request_payment(request, pk):
    submission = get_object_or_404(Submission, pk=pk)

    if submission.active_fee is None:
        messages.info(request, 'This journal has no active publication fee.')
        return redirect('admin_submission_detail', pk=pk)
    if submission.is_paid:
        messages.info(request, 'The publication fee is already settled.')
        return redirect('admin_submission_detail', pk=pk)

    ensure_payment_requested(submission, request)
    messages.success(request, 'The author has been notified to pay the publication fee.')
    return redirect('admin_submission_detail', pk=pk)


@journal_staff_required(roles=DECISION_ROLES)
@require_POST
def waive_payment(request, pk):
    submission = get_object_or_404(Submission, pk=pk)
    reason = request.POST.get('reason', '').strip()

    fee = submission.active_fee
    payment = _pending_payment(submission) or Payment.objects.create(
        submission=submission, author=submission.author,
        amount=fee.amount if fee else 0,
        currency=fee.currency if fee else 'NGN',
        reference=_new_reference(),
    )
    payment.status = 'waived'
    payment.waived_by = request.user
    payment.waiver_reason = reason
    payment.save()

    if submission.status == 'awaiting_payment':
        submission.status = 'approved'
        submission.save(update_fields=['status'])

    from .submission_views import log_submission_action
    log_submission_action(submission, request.user, 'Publication fee waived', {'reason': reason})
    messages.success(request, 'Publication fee waived. The article can now be published.')
    return redirect('admin_submission_detail', pk=pk)


# ---------------------------------------------------------------------------
# Author: pay
# ---------------------------------------------------------------------------

@login_required
@require_POST
def pay(request, pk):
    submission = get_object_or_404(Submission, pk=pk, author=request.user)

    if not submission.requires_payment:
        messages.info(request, 'No payment is due for this submission.')
        return redirect('submission_detail', pk=pk)

    if not paystack.is_configured():
        messages.error(request, 'Online payment is not available right now. Please contact the editorial office.')
        return redirect('submission_detail', pk=pk)

    payment = _pending_payment(submission) or ensure_payment_requested(submission, request)

    callback_url = settings.PAYSTACK_CALLBACK_URL or request.build_absolute_uri(reverse('paystack_callback'))
    data = paystack.initialize_transaction(
        email=request.user.email,
        amount_kobo=payment.amount_kobo,
        reference=payment.reference,
        callback_url=callback_url,
        metadata={'submission_id': submission.pk, 'payment_id': payment.pk},
    )
    if not data or 'authorization_url' not in data:
        messages.error(request, 'We could not start the payment. Please try again shortly.')
        return redirect('submission_detail', pk=pk)

    return redirect(data['authorization_url'])


@login_required
def paystack_callback(request):
    """Browser return from Paystack. Verifies server-side, then shows a result."""
    reference = request.GET.get('reference') or request.GET.get('trxref')
    if not reference:
        messages.error(request, 'Missing payment reference.')
        return redirect('dashboard')

    payment = get_object_or_404(Payment, reference=reference)
    # Only the paying author may resolve their own payment here.
    if payment.author != request.user and not has_journal_role(
        request.user, payment.submission.journal, roles=DECISION_ROLES
    ):
        messages.error(request, 'You cannot view this payment.')
        return redirect('dashboard')

    data = paystack.verify_transaction(reference)
    if data and data.get('status') == 'success':
        _mark_success(payment, data)
        messages.success(request, 'Payment received — thank you. Your article will be published shortly.')
    else:
        messages.warning(request, 'Payment not confirmed yet. If you completed it, we will update automatically.')

    return redirect('submission_detail', pk=payment.submission.pk)


@csrf_exempt
@require_POST
def paystack_webhook(request):
    """Authoritative payment confirmation from Paystack."""
    signature = request.headers.get('x-paystack-signature', '')
    if not paystack.verify_webhook_signature(request.body, signature):
        logger.warning('Rejected Paystack webhook with bad signature')
        return HttpResponseBadRequest('Invalid signature')

    try:
        event = json.loads(request.body.decode('utf-8'))
    except (ValueError, UnicodeDecodeError):
        return HttpResponseBadRequest('Invalid payload')

    if event.get('event') == 'charge.success':
        data = event.get('data', {})
        reference = data.get('reference')
        payment = Payment.objects.filter(reference=reference).first()
        if payment:
            _mark_success(payment, data)

    # Always 200 so Paystack stops retrying a handled event.
    return HttpResponse(status=200)
