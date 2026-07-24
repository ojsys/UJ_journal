"""
Per-journal permission helpers.

Editorial views used to be gated on Django's site-wide ``is_staff`` flag, which
meant any staff member could act on any journal. These helpers narrow that to
"which journals may this user act on, and in what capacity", while keeping
superusers and existing ``is_staff`` users fully privileged so nothing that
works today stops working.

Two ideas only:

* :func:`has_journal_role` — may this user act on *this* journal?
* :func:`journals_for`     — which journals may this user act on? (for filtering
  querysets, so a journal editor's submission list shows only their own)

The :func:`journal_staff_required` decorator wraps both for view use.
"""
from functools import wraps

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect

from .models import Journal, JournalRole, Submission

# Roles that may manage journal content (rubrics, checklist, team) — the lead
# only. The chief editor is the single per-journal admin.
CONTENT_ROLES = (JournalRole.ROLE_CHIEF_EDITOR,)

# Roles that may run the review workflow.
WORKFLOW_ROLES = (JournalRole.ROLE_CHIEF_EDITOR, JournalRole.ROLE_EDITOR)

# Roles that may take final decisions (approve, publish, reject).
DECISION_ROLES = (JournalRole.ROLE_CHIEF_EDITOR,)

# Any journal-scoped role at all.
ANY_ROLE = tuple(choice[0] for choice in JournalRole.ROLE_CHOICES)


def is_site_admin(user):
    """Site-wide staff — unrestricted across every journal."""
    return bool(
        user
        and user.is_authenticated
        and (user.is_superuser or user.is_staff)
    )


def has_journal_role(user, journal, roles=None):
    """Return ``True`` if ``user`` may act on ``journal`` in one of ``roles``.

    ``roles=None`` means "any journal role". Site admins always pass.
    """
    if not (user and user.is_authenticated):
        return False
    if is_site_admin(user):
        return True
    if journal is None:
        return False

    qs = JournalRole.objects.filter(user=user, journal=journal)
    if roles:
        qs = qs.filter(role__in=roles)
    return qs.exists()


def journals_for(user, roles=None):
    """Journals ``user`` may act on, as a queryset.

    Site admins get every journal. Everyone else gets the journals they hold a
    matching role on — an empty queryset if they hold none.
    """
    if not (user and user.is_authenticated):
        return Journal.objects.none()
    if is_site_admin(user):
        return Journal.objects.all()

    qs = JournalRole.objects.filter(user=user)
    if roles:
        qs = qs.filter(role__in=roles)
    return Journal.objects.filter(pk__in=qs.values('journal_id'))


def roles_on(user, journal):
    """The role codes ``user`` holds on ``journal`` (site admins get them all)."""
    if not (user and user.is_authenticated):
        return []
    if is_site_admin(user):
        return list(ANY_ROLE)
    return list(
        JournalRole.objects
        .filter(user=user, journal=journal)
        .values_list('role', flat=True)
    )


def can_manage_any_journal(user, roles=None):
    """Whether the user has editorial standing anywhere — used to show nav links."""
    if is_site_admin(user):
        return True
    return journals_for(user, roles=roles).exists()


def _resolve_journal(request, view_kwargs):
    """Work out which journal a view is about, from its URL kwargs.

    Handles the three shapes used in this codebase: an explicit journal id, a
    submission pk (journal comes from the submission), and a journal pk.
    """
    for key in ('journal_id', 'journal_pk'):
        if key in view_kwargs:
            return get_object_or_404(Journal, pk=view_kwargs[key])

    for key in ('submission_id', 'submission_pk'):
        if key in view_kwargs:
            return get_object_or_404(Submission, pk=view_kwargs[key]).journal

    if 'pk' in view_kwargs:
        # Ambiguous by itself, so the decorator's `lookup` argument disambiguates.
        return None

    return None


def journal_staff_required(roles=None, lookup='submission'):
    """Require a journal-scoped role for the journal this view is about.

    ``lookup`` says how to read a bare ``pk`` kwarg:

    * ``'submission'`` — ``pk`` is a Submission id; use its journal (default,
      because most editorial views are submission-scoped).
    * ``'journal'``    — ``pk`` is a Journal id.
    * ``'none'``       — the view is not about one journal (e.g. a list view);
      only check that the user has the role on *some* journal, and let the view
      filter its own queryset with :func:`journals_for`.

    Unauthenticated users are redirected to log in; authenticated users without
    the role get a 403 rather than a redirect, so a missing permission is never
    mistaken for a missing page.
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            user = request.user
            if not (user and user.is_authenticated):
                return redirect(f'/login/?next={request.path}')

            if is_site_admin(user):
                return view_func(request, *args, **kwargs)

            if lookup == 'none':
                if not can_manage_any_journal(user, roles=roles):
                    raise PermissionDenied(
                        "You do not have an editorial role on any journal."
                    )
                return view_func(request, *args, **kwargs)

            journal = _resolve_journal(request, kwargs)
            if journal is None and 'pk' in kwargs:
                if lookup == 'journal':
                    journal = get_object_or_404(Journal, pk=kwargs['pk'])
                else:
                    journal = get_object_or_404(Submission, pk=kwargs['pk']).journal

            if not has_journal_role(user, journal, roles=roles):
                raise PermissionDenied(
                    "You do not have permission to manage this journal."
                )

            return view_func(request, *args, **kwargs)
        return _wrapped
    return decorator
