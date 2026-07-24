"""
Template helpers for blind-review-safe rendering.

Templates that show a submission to a reviewer must never print the author's
name directly. These filters route through ``Submission.is_author_hidden_from``
so the identity decision lives in one place (the model), not scattered across
``{% if assignment.blinded %}`` branches that a single wrong ``{% else %}`` could
leak through.

Usage::

    {% load journal_extras %}
    {{ submission|author_label:request.user }}
    {% if submission|author_hidden:request.user %} … {% endif %}
"""
from django import template

register = template.Library()


@register.filter
def author_label(submission, user):
    """The author's name for ``user``, or the manuscript code if hidden."""
    return submission.author_label_for(user)


@register.filter
def author_hidden(submission, user):
    """True if the author's identity must be hidden from ``user``."""
    return submission.is_author_hidden_from(user)
