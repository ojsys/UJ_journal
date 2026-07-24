"""
Volunteer peer-reviewer portal.

Public side: anyone can apply to review, no account needed.
Editorial side: staff review applications and, on approval, turn an applicant
into either a login account or a token-based guest reviewer — reusing the
existing guest-invite machinery.
"""
import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import EmailMultiAlternatives
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.html import strip_tags
from django.utils.http import urlsafe_base64_encode
from django.views.decorators.http import require_POST

from .forms import ReviewerApplicationDecisionForm, ReviewerApplicationForm
from .models import CustomUser, GuestReviewer, Journal, Profile, ReviewerApplication
from .permissions import WORKFLOW_ROLES, is_site_admin, journal_staff_required
from .utils import get_from_email

logger = logging.getLogger('journalapp')


# ---------------------------------------------------------------------------
# Email helpers
# ---------------------------------------------------------------------------

def _send(subject, template, context, to):
    html = render_to_string(template, context)
    email = EmailMultiAlternatives(
        subject=subject, body=strip_tags(html),
        from_email=get_from_email(), to=to,
    )
    email.attach_alternative(html, "text/html")
    email.send()


def _notify_editors_of_application(application, request):
    """Tell editorial staff a new application arrived."""
    recipients = set(
        CustomUser.objects.filter(is_staff=True, is_active=True)
        .values_list('email', flat=True)
    )
    recipients.update(
        CustomUser.objects.filter(
            is_active=True,
            journal_roles__role__in=WORKFLOW_ROLES,
        ).values_list('email', flat=True)
    )
    if not recipients:
        return
    _send(
        subject=f'New reviewer application — {application.get_full_name()}',
        template='emails/reviewer_application_admin.html',
        context={
            'application': application,
            'manage_url': request.build_absolute_uri(
                reverse('reviewer_application_detail', args=[application.pk])
            ),
        },
        to=list(recipients),
    )


# ---------------------------------------------------------------------------
# Public application
# ---------------------------------------------------------------------------

def reviewer_apply(request):
    """Public page to apply as a volunteer peer reviewer."""
    if request.method == 'POST':
        form = ReviewerApplicationForm(request.POST, request.FILES)

        # Lightweight per-session throttle: one submission every few minutes.
        last = request.session.get('reviewer_apply_ts')
        now = timezone.now().timestamp()
        throttled = last and (now - last) < 120

        if throttled:
            messages.error(request, 'Please wait a moment before submitting again.')
        elif form.is_valid():
            application = form.save()
            request.session['reviewer_apply_ts'] = now

            # Confirmation to the applicant (best-effort).
            try:
                _send(
                    subject='We received your reviewer application',
                    template='emails/reviewer_application_confirmation.html',
                    context={'application': application},
                    to=[application.email],
                )
            except Exception:
                logger.error('Reviewer application confirmation email failed', exc_info=True)

            try:
                _notify_editors_of_application(application, request)
            except Exception:
                logger.error('Reviewer application admin notification failed', exc_info=True)

            return redirect('reviewer_apply_thanks')
    else:
        form = ReviewerApplicationForm()

    return render(request, 'reviewers/apply.html', {
        'form': form,
        'journals': Journal.objects.select_related('department').order_by('name'),
    })


def reviewer_apply_thanks(request):
    return render(request, 'reviewers/apply_thanks.html')


# ---------------------------------------------------------------------------
# Editorial management
# ---------------------------------------------------------------------------

@journal_staff_required(roles=WORKFLOW_ROLES, lookup='none')
def reviewer_applications_list(request):
    applications = ReviewerApplication.objects.all().prefetch_related('journals_of_interest')

    status_filter = request.GET.get('status', 'pending')
    if status_filter in dict(ReviewerApplication.STATUS_CHOICES):
        applications = applications.filter(status=status_filter)

    return render(request, 'reviewers/applications_list.html', {
        'applications': applications,
        'status_filter': status_filter,
        'status_choices': ReviewerApplication.STATUS_CHOICES,
        'pending_count': ReviewerApplication.objects.filter(status='pending').count(),
    })


@journal_staff_required(roles=WORKFLOW_ROLES, lookup='none')
def reviewer_application_detail(request, pk):
    application = get_object_or_404(ReviewerApplication, pk=pk)
    return render(request, 'reviewers/application_detail.html', {
        'application': application,
        'form': ReviewerApplicationDecisionForm(),
    })


@journal_staff_required(roles=WORKFLOW_ROLES, lookup='none')
@require_POST
def reviewer_application_decide(request, pk):
    application = get_object_or_404(ReviewerApplication, pk=pk)

    if application.status != 'pending':
        messages.info(request, 'This application has already been decided.')
        return redirect('reviewer_application_detail', pk=pk)

    form = ReviewerApplicationDecisionForm(request.POST)
    if not form.is_valid():
        messages.error(request, 'Please choose a decision.')
        return redirect('reviewer_application_detail', pk=pk)

    decision = form.cleaned_data['decision']
    notes = form.cleaned_data.get('notes', '')

    if decision == 'reject':
        _reject(application, request, notes)
    elif decision == 'approve_user':
        _approve_as_user(application, request, notes)
    elif decision == 'approve_guest':
        _approve_as_guest(application, request, notes)

    return redirect('reviewer_application_detail', pk=pk)


def _finalise(application, request, notes, status):
    application.status = status
    application.review_notes = notes
    application.reviewed_by = request.user
    application.reviewed_at = timezone.now()
    application.save()


def _reject(application, request, notes):
    _finalise(application, request, notes, 'rejected')
    try:
        _send(
            subject='Update on your reviewer application',
            template='emails/reviewer_application_rejected.html',
            context={'application': application, 'notes': notes},
            to=[application.email],
        )
    except Exception:
        logger.error('Reviewer rejection email failed', exc_info=True)
    messages.success(request, 'Application declined and the applicant notified.')


def _approve_as_user(application, request, notes):
    """Turn the applicant into a login account with reviewer rights."""
    existing = CustomUser.objects.filter(email__iexact=application.email).first()

    if existing:
        user = existing
        profile, _ = Profile.objects.get_or_create(user=user)
        profile.is_reviewer = True
        profile.save(update_fields=['is_reviewer'])
        set_password_url = None
    else:
        user = CustomUser.objects.create(
            email=application.email.lower(),
            first_name=application.first_name,
            last_name=application.last_name,
            is_active=True,
        )
        user.set_unusable_password()
        user.save()
        # Profile is created by a post_save signal; ensure the flag is set.
        profile, _ = Profile.objects.get_or_create(user=user)
        profile.is_reviewer = True
        profile.save(update_fields=['is_reviewer'])
        # A set-password link using the standard token flow (reuses the existing
        # password_reset_confirm page — no reliance on a reset-email template).
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        set_password_url = request.build_absolute_uri(
            reverse('password_reset_confirm', kwargs={'uidb64': uid, 'token': token})
        )

    application.created_user = user
    _finalise(application, request, notes, 'approved')

    try:
        _send(
            subject='You are now a reviewer',
            template='emails/reviewer_application_approved_user.html',
            context={
                'application': application,
                'notes': notes,
                'set_password_url': set_password_url,
                'login_url': request.build_absolute_uri(reverse('login')),
            },
            to=[application.email],
        )
    except Exception:
        logger.error('Reviewer approval (user) email failed', exc_info=True)

    messages.success(
        request,
        f'{application.get_full_name()} approved as a reviewer with a login account.'
    )


def _approve_as_guest(application, request, notes):
    """Turn the applicant into a token-based guest reviewer."""
    guest = GuestReviewer.objects.filter(email__iexact=application.email).first()
    if not guest:
        guest = GuestReviewer.objects.create(
            email=application.email.lower(),
            first_name=application.first_name,
            last_name=application.last_name,
            affiliation=application.affiliation,
            expertise_areas=application.expertise_areas,
            created_by=request.user,
        )

    application.guest_reviewer = guest
    _finalise(application, request, notes, 'approved')

    # Reuse the existing guest-invite email.
    from .submission_views import send_guest_invitation_email
    try:
        send_guest_invitation_email(guest, request)
    except Exception:
        logger.error('Reviewer approval (guest) invitation failed', exc_info=True)

    messages.success(
        request,
        f'{application.get_full_name()} approved and added as a guest reviewer; '
        f'an invitation was sent.'
    )
