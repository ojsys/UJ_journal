from .models import Journal, SiteSettings
from .permissions import CONTENT_ROLES, WORKFLOW_ROLES, can_manage_any_journal


def site_settings(request):
    try:
        settings = SiteSettings.objects.first()
        if not settings:
            settings = SiteSettings.objects.create()
    except:
        settings = None

    return {'site_settings': settings}


def journal_roles(request):
    """Expose editorial standing to templates.

    Navigation used to key off ``user.is_staff``, which hides the editorial
    menu from a journal chief editor who isn't site staff. These two flags let
    the nav ask "can this user manage anything?" instead.
    """
    user = getattr(request, 'user', None)
    if not (user and user.is_authenticated):
        return {'can_manage_journals': False, 'can_manage_journal_content': False}

    return {
        # Runs the review workflow on at least one journal.
        'can_manage_journals': can_manage_any_journal(user, roles=WORKFLOW_ROLES),
        # Manages journal content (rubrics, checklist, team) on at least one.
        'can_manage_journal_content': can_manage_any_journal(user, roles=CONTENT_ROLES),
    }


def nav_journals(request):
    """The journals to list in the main navigation dropdown.

    The nav used to link to a single flat journal list. Since the portal now
    fronts three separate journals, every page offers them directly.
    """
    return {
        'nav_journals': Journal.objects.filter(is_active=True).only(
            'name', 'slug', 'abbreviation'
        )
    }
