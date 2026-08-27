"""
Tests for per-journal editorial roles (Phase 1).

The point of JournalRole is isolation: an editor on Journal A must not be able
to see or act on Journal B. These tests assert that boundary through the views,
because the failure that matters is a leak in a response, not a wrong return
value from a helper.
"""
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from .models import Department, Journal, JournalRole, Submission
from .permissions import has_journal_role, journals_for

User = get_user_model()


class JournalRoleTestCase(TestCase):
    """Two journals, one chief editor on each, one submission apiece."""

    def setUp(self):
        self.dept = Department.objects.create(name='English', code='ENG')
        self.journal_a = Journal.objects.create(
            department=self.dept, name='Journal A', slug='journal-a', abbreviation='JA')
        self.journal_b = Journal.objects.create(
            department=self.dept, name='Journal B', slug='journal-b', abbreviation='JB')

        self.author = User.objects.create_user('author@test.ng', 'pw12345!')
        self.editor_a = User.objects.create_user('editor.a@test.ng', 'pw12345!')
        self.editor_b = User.objects.create_user('editor.b@test.ng', 'pw12345!')
        self.outsider = User.objects.create_user('nobody@test.ng', 'pw12345!')
        self.site_staff = User.objects.create_user('staff@test.ng', 'pw12345!', is_staff=True)

        JournalRole.objects.create(
            user=self.editor_a, journal=self.journal_a, role=JournalRole.ROLE_CHIEF_EDITOR
        )
        JournalRole.objects.create(
            user=self.editor_b, journal=self.journal_b, role=JournalRole.ROLE_CHIEF_EDITOR
        )

        self.sub_a = self._submission(self.journal_a, 'Paper in A')
        self.sub_b = self._submission(self.journal_b, 'Paper in B')

    def _submission(self, journal, title):
        return Submission.objects.create(
            author=self.author,
            journal=journal,
            title=title,
            document=SimpleUploadedFile(f'{title}.docx', b'stub'),
        )


class PermissionHelperTests(JournalRoleTestCase):

    def test_role_grants_access_to_own_journal_only(self):
        self.assertTrue(has_journal_role(self.editor_a, self.journal_a))
        self.assertFalse(has_journal_role(self.editor_a, self.journal_b))

    def test_site_staff_pass_for_every_journal(self):
        self.assertTrue(has_journal_role(self.site_staff, self.journal_a))
        self.assertTrue(has_journal_role(self.site_staff, self.journal_b))

    def test_user_without_a_role_has_none(self):
        self.assertFalse(has_journal_role(self.outsider, self.journal_a))
        self.assertEqual(list(journals_for(self.outsider)), [])

    def test_journals_for_returns_only_granted_journals(self):
        self.assertEqual(list(journals_for(self.editor_a)), [self.journal_a])
        # Site staff see every journal, including the three the data migration
        # seeds (JJEL, JOJWOL, Humanity) — not just the two built in setUp.
        self.assertEqual(
            set(journals_for(self.site_staff)),
            set(Journal.objects.all()),
        )
        self.assertLessEqual(
            {self.journal_a, self.journal_b},
            set(journals_for(self.site_staff)),
        )

    def test_role_filter_is_respected(self):
        # editor_a is a chief editor, not a plain editor
        self.assertTrue(has_journal_role(
            self.editor_a, self.journal_a, roles=(JournalRole.ROLE_CHIEF_EDITOR,)
        ))
        self.assertFalse(has_journal_role(
            self.editor_a, self.journal_a, roles=(JournalRole.ROLE_EDITOR,)
        ))


class SubmissionListScopingTests(JournalRoleTestCase):

    def test_editor_sees_only_own_journal_submissions(self):
        self.client.force_login(self.editor_a)
        response = self.client.get(reverse('admin_submission_list'), HTTP_HOST='localhost')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Paper in A')
        self.assertNotContains(response, 'Paper in B')

    def test_journal_query_param_cannot_escape_the_scope(self):
        """?journal=<other journal> must return nothing, not the other journal."""
        self.client.force_login(self.editor_a)
        response = self.client.get(
            reverse('admin_submission_list'),
            {'journal': self.journal_b.pk},
            HTTP_HOST='localhost',
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Paper in B')

    def test_site_staff_see_every_journal(self):
        self.client.force_login(self.site_staff)
        response = self.client.get(reverse('admin_submission_list'), HTTP_HOST='localhost')

        self.assertContains(response, 'Paper in A')
        self.assertContains(response, 'Paper in B')

    def test_outsider_is_denied(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('admin_submission_list'), HTTP_HOST='localhost')
        self.assertEqual(response.status_code, 403)


class SubmissionDetailScopingTests(JournalRoleTestCase):

    def test_editor_can_open_own_journal_submission(self):
        self.client.force_login(self.editor_a)
        response = self.client.get(
            reverse('admin_submission_detail', args=[self.sub_a.pk]), HTTP_HOST='localhost'
        )
        self.assertEqual(response.status_code, 200)

    def test_editor_is_denied_another_journals_submission(self):
        self.client.force_login(self.editor_a)
        response = self.client.get(
            reverse('admin_submission_detail', args=[self.sub_b.pk]), HTTP_HOST='localhost'
        )
        self.assertEqual(response.status_code, 403)

    def test_anonymous_is_redirected_to_login(self):
        response = self.client.get(
            reverse('admin_submission_detail', args=[self.sub_a.pk]), HTTP_HOST='localhost'
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response['Location'])


class DecisionRoleTests(JournalRoleTestCase):
    """Editors assist; only chief editors take final decisions."""

    def setUp(self):
        super().setUp()
        self.plain_editor = User.objects.create_user('plain@test.ng', 'pw12345!')
        JournalRole.objects.create(
            user=self.plain_editor, journal=self.journal_a, role=JournalRole.ROLE_EDITOR
        )

    def test_plain_editor_cannot_reject(self):
        self.client.force_login(self.plain_editor)
        response = self.client.post(
            reverse('reject_submission', args=[self.sub_a.pk]),
            {'reason': 'no'}, HTTP_HOST='localhost',
        )
        self.assertEqual(response.status_code, 403)
        self.sub_a.refresh_from_db()
        self.assertNotEqual(self.sub_a.status, 'rejected')

    def test_chief_editor_can_reject(self):
        self.client.force_login(self.editor_a)
        response = self.client.post(
            reverse('reject_submission', args=[self.sub_a.pk]),
            {'reason': 'out of scope'}, HTTP_HOST='localhost',
        )
        self.assertEqual(response.status_code, 302)
        self.sub_a.refresh_from_db()
        self.assertEqual(self.sub_a.status, 'rejected')

    def test_plain_editor_can_still_open_the_submission(self):
        self.client.force_login(self.plain_editor)
        response = self.client.get(
            reverse('admin_submission_detail', args=[self.sub_a.pk]), HTTP_HOST='localhost'
        )
        self.assertEqual(response.status_code, 200)


class JournalTeamViewTests(JournalRoleTestCase):

    # The chief editor (editor_a, from the base fixture) manages the team.

    def test_chief_editor_can_grant_a_role(self):
        self.client.force_login(self.editor_a)
        response = self.client.post(
            reverse('journal_team', args=[self.journal_a.pk]),
            {'email': self.outsider.email, 'role': JournalRole.ROLE_EDITOR},
            HTTP_HOST='localhost',
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            JournalRole.objects.filter(
                user=self.outsider, journal=self.journal_a, role=JournalRole.ROLE_EDITOR
            ).exists()
        )

    def test_granting_records_who_granted_it(self):
        self.client.force_login(self.editor_a)
        self.client.post(
            reverse('journal_team', args=[self.journal_a.pk]),
            {'email': self.outsider.email, 'role': JournalRole.ROLE_EDITOR},
            HTTP_HOST='localhost',
        )
        role = JournalRole.objects.get(user=self.outsider, journal=self.journal_a)
        self.assertEqual(role.granted_by, self.editor_a)

    def test_unknown_email_is_rejected(self):
        self.client.force_login(self.editor_a)
        response = self.client.post(
            reverse('journal_team', args=[self.journal_a.pk]),
            {'email': 'ghost@test.ng', 'role': JournalRole.ROLE_EDITOR},
            HTTP_HOST='localhost',
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'No account with that email')

    def test_plain_editor_cannot_manage_the_team(self):
        """Only chief editors (and site staff) manage the team; editors can't."""
        plain = User.objects.create_user('plain2@test.ng', 'pw12345!')
        JournalRole.objects.create(
            user=plain, journal=self.journal_a, role=JournalRole.ROLE_EDITOR
        )
        self.client.force_login(plain)
        response = self.client.get(
            reverse('journal_team', args=[self.journal_a.pk]), HTTP_HOST='localhost'
        )
        self.assertEqual(response.status_code, 403)

    def test_chief_editor_cannot_manage_another_journals_team(self):
        self.client.force_login(self.editor_a)
        response = self.client.get(
            reverse('journal_team', args=[self.journal_b.pk]), HTTP_HOST='localhost'
        )
        self.assertEqual(response.status_code, 403)

    def test_last_chief_editor_cannot_revoke_themselves(self):
        role = JournalRole.objects.get(
            user=self.editor_a, journal=self.journal_a, role=JournalRole.ROLE_CHIEF_EDITOR
        )
        self.client.force_login(self.editor_a)
        response = self.client.post(
            reverse('journal_role_revoke', args=[self.journal_a.pk, role.pk]),
            HTTP_HOST='localhost',
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(JournalRole.objects.filter(pk=role.pk).exists())

    def test_revoke_works_when_another_chief_editor_remains(self):
        JournalRole.objects.create(
            user=self.outsider, journal=self.journal_a, role=JournalRole.ROLE_CHIEF_EDITOR
        )
        role = JournalRole.objects.get(
            user=self.editor_a, journal=self.journal_a, role=JournalRole.ROLE_CHIEF_EDITOR
        )
        self.client.force_login(self.editor_a)
        self.client.post(
            reverse('journal_role_revoke', args=[self.journal_a.pk, role.pk]),
            HTTP_HOST='localhost',
        )
        self.assertFalse(JournalRole.objects.filter(pk=role.pk).exists())

    def test_duplicate_role_is_rejected(self):
        self.client.force_login(self.editor_a)
        response = self.client.post(
            reverse('journal_team', args=[self.journal_a.pk]),
            {'email': self.editor_a.email, 'role': JournalRole.ROLE_CHIEF_EDITOR},
            HTTP_HOST='localhost',
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'already')
        self.assertEqual(
            JournalRole.objects.filter(
                user=self.editor_a, journal=self.journal_a,
                role=JournalRole.ROLE_CHIEF_EDITOR,
            ).count(),
            1,
        )


class AdminDashboardScopingTests(JournalRoleTestCase):

    def test_editor_dashboard_counts_exclude_other_journals(self):
        self.client.force_login(self.editor_a)
        response = self.client.get(reverse('admin_dashboard'), HTTP_HOST='localhost')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['submission_stats']['total'], 1)
        journals_shown = [row['journal'] for row in response.context['journal_stats']]
        self.assertEqual(journals_shown, [self.journal_a])

    def test_site_staff_dashboard_counts_everything(self):
        self.client.force_login(self.site_staff)
        response = self.client.get(reverse('admin_dashboard'), HTTP_HOST='localhost')
        self.assertEqual(response.context['submission_stats']['total'], 2)

    def test_plain_author_is_sent_to_author_dashboard(self):
        self.client.force_login(self.author)
        response = self.client.get(reverse('dashboard'), HTTP_HOST='localhost')
        self.assertRedirects(
            response, reverse('author_dashboard'),
            fetch_redirect_response=False,
        )

    def test_journal_editor_is_sent_to_admin_dashboard(self):
        self.client.force_login(self.editor_a)
        response = self.client.get(reverse('dashboard'), HTTP_HOST='localhost')
        self.assertRedirects(
            response, reverse('admin_dashboard'),
            fetch_redirect_response=False,
        )


# ---------------------------------------------------------------------------
# Phase 2: journal content (rubrics, checklist, public journal page)
# ---------------------------------------------------------------------------

from .models import Rubric, ChecklistItem, ChecklistResponse


class RubricManagementTests(JournalRoleTestCase):

    def test_chief_editor_can_add_a_rubric(self):
        self.client.force_login(self.editor_a)
        response = self.client.post(
            reverse('journal_rubrics', args=[self.journal_a.pk]),
            {'title': 'Originality', 'content': 'Is it novel?', 'order': 0},
            HTTP_HOST='localhost',
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Rubric.objects.filter(journal=self.journal_a, title='Originality').exists())

    def test_plain_editor_cannot_manage_rubrics(self):
        plain = User.objects.create_user('ed@test.ng', 'pw12345!')
        JournalRole.objects.create(user=plain, journal=self.journal_a, role=JournalRole.ROLE_EDITOR)
        self.client.force_login(plain)
        response = self.client.get(reverse('journal_rubrics', args=[self.journal_a.pk]), HTTP_HOST='localhost')
        self.assertEqual(response.status_code, 403)

    def test_editor_cannot_add_rubric_to_another_journal(self):
        self.client.force_login(self.editor_a)
        response = self.client.post(
            reverse('journal_rubrics', args=[self.journal_b.pk]),
            {'title': 'X', 'content': 'Y', 'order': 0},
            HTTP_HOST='localhost',
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Rubric.objects.filter(journal=self.journal_b).exists())

    def test_rubric_delete(self):
        rubric = Rubric.objects.create(journal=self.journal_a, title='Temp', content='x')
        self.client.force_login(self.editor_a)
        response = self.client.post(
            reverse('rubric_delete', args=[self.journal_a.pk, rubric.pk]), HTTP_HOST='localhost'
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Rubric.objects.filter(pk=rubric.pk).exists())


class ChecklistManagementTests(JournalRoleTestCase):

    def test_chief_editor_can_add_a_checklist_item(self):
        self.client.force_login(self.editor_a)
        response = self.client.post(
            reverse('journal_checklist', args=[self.journal_a.pk]),
            {'text': 'Formatting followed', 'help_text': '', 'required': 'on',
             'is_active': 'on', 'order': 0},
            HTTP_HOST='localhost',
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(ChecklistItem.objects.filter(journal=self.journal_a, text='Formatting followed').exists())

    def test_delete_deactivates_item_with_responses(self):
        item = ChecklistItem.objects.create(journal=self.journal_a, text='Confirmed')
        ChecklistResponse.objects.create(
            submission=self.sub_a, item=item, item_text=item.text, checked=True
        )
        self.client.force_login(self.editor_a)
        self.client.post(
            reverse('checklist_item_delete', args=[self.journal_a.pk, item.pk]), HTTP_HOST='localhost'
        )
        item.refresh_from_db()
        self.assertFalse(item.is_active)  # deactivated, not deleted
        self.assertTrue(ChecklistItem.objects.filter(pk=item.pk).exists())

    def test_delete_removes_unanswered_item(self):
        item = ChecklistItem.objects.create(journal=self.journal_a, text='Unused')
        self.client.force_login(self.editor_a)
        self.client.post(
            reverse('checklist_item_delete', args=[self.journal_a.pk, item.pk]), HTTP_HOST='localhost'
        )
        self.assertFalse(ChecklistItem.objects.filter(pk=item.pk).exists())


class SubmissionChecklistTests(JournalRoleTestCase):

    def setUp(self):
        super().setUp()
        self.required_item = ChecklistItem.objects.create(
            journal=self.journal_a, text='I confirm formatting', required=True
        )
        self.optional_item = ChecklistItem.objects.create(
            journal=self.journal_a, text='Suggested reviewers included', required=False
        )

    def _post(self, data):
        from django.core.files.uploadedfile import SimpleUploadedFile
        data['document'] = SimpleUploadedFile('paper.docx', b'stub')
        self.client.force_login(self.author)
        return self.client.post(reverse('submission_create'), data, HTTP_HOST='localhost')

    def test_submission_blocked_without_required_item(self):
        before = Submission.objects.count()
        response = self._post({'journal': self.journal_a.pk, 'cover_letter': ''})
        self.assertEqual(response.status_code, 200)  # re-render with error
        self.assertContains(response, 'every required checklist item')
        self.assertEqual(Submission.objects.count(), before)

    def test_submission_succeeds_with_required_item_ticked(self):
        response = self._post({
            'journal': self.journal_a.pk, 'cover_letter': '',
            f'checklist_{self.required_item.pk}': '1',
        })
        self.assertEqual(response.status_code, 302)
        sub = Submission.objects.filter(journal=self.journal_a).latest('submitted_at')
        # Both active items get a response row; required one is checked.
        self.assertEqual(sub.checklist_responses.count(), 2)
        req = sub.checklist_responses.get(item=self.required_item)
        self.assertTrue(req.checked)
        self.assertEqual(req.item_text, 'I confirm formatting')  # frozen copy
        opt = sub.checklist_responses.get(item=self.optional_item)
        self.assertFalse(opt.checked)

    def test_journal_without_checklist_submits_freely(self):
        response = self._post({'journal': self.journal_b.pk, 'cover_letter': ''})
        self.assertEqual(response.status_code, 302)


class JournalDetailPageTests(JournalRoleTestCase):

    def test_public_journal_page_shows_rubrics_and_active_checklist(self):
        Rubric.objects.create(journal=self.journal_a, title='Clarity', content='Well written?')
        ChecklistItem.objects.create(journal=self.journal_a, text='Live item', is_active=True)
        ChecklistItem.objects.create(journal=self.journal_a, text='Retired item', is_active=False)

        response = self.client.get(
            reverse('journal_home', args=[self.journal_a.slug]), HTTP_HOST='localhost')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Clarity')
        self.assertContains(response, 'Live item')
        self.assertNotContains(response, 'Retired item')  # inactive hidden from public

    def test_old_numeric_journal_url_redirects_to_the_slug(self):
        response = self.client.get(
            reverse('journal_detail', args=[self.journal_a.pk]), HTTP_HOST='localhost')
        self.assertRedirects(
            response,
            reverse('journal_home', args=[self.journal_a.slug]),
            status_code=301,
        )

    def test_inactive_journal_is_hidden_from_the_public(self):
        self.journal_a.is_active = False
        self.journal_a.save(update_fields=['is_active'])
        response = self.client.get(
            reverse('journal_home', args=[self.journal_a.slug]), HTTP_HOST='localhost')
        self.assertEqual(response.status_code, 404)


# ---------------------------------------------------------------------------
# Phase 3: author experience (edit/re-upload, statuses removed, wording)
# ---------------------------------------------------------------------------

from .models import DocumentVersion


class SubmissionEditTests(JournalRoleTestCase):

    def test_editable_states(self):
        for status in ['pending', 'in_review', 'with_editor', 'revision_requested', 'revised']:
            self.sub_a.status = status
            self.assertTrue(self.sub_a.is_editable_by_author, status)
        for status in ['approved', 'published', 'rejected']:
            self.sub_a.status = status
            self.assertFalse(self.sub_a.is_editable_by_author, status)

    def test_author_can_edit_title_and_cover_letter(self):
        self.sub_a.status = 'pending'; self.sub_a.save()
        self.client.force_login(self.author)
        response = self.client.post(
            reverse('submission_edit', args=[self.sub_a.pk]),
            {'title': 'Corrected title', 'cover_letter': 'Fixed a typo'},
            HTTP_HOST='localhost',
        )
        self.assertEqual(response.status_code, 302)
        self.sub_a.refresh_from_db()
        self.assertEqual(self.sub_a.title, 'Corrected title')
        self.assertEqual(self.sub_a.status, 'pending')  # a plain edit does not change status

    def test_reupload_adds_a_new_version(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        self.sub_a.status = 'in_review'; self.sub_a.save()
        before = self.sub_a.document_versions.count()
        self.client.force_login(self.author)
        response = self.client.post(
            reverse('submission_edit', args=[self.sub_a.pk]),
            {
                'title': self.sub_a.title, 'cover_letter': '',
                'new_document': SimpleUploadedFile('fixed.docx', b'newer'),
            },
            HTTP_HOST='localhost',
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.sub_a.document_versions.count(), before + 1)

    def test_edit_blocked_after_acceptance(self):
        self.sub_a.status = 'approved'; self.sub_a.save()
        self.client.force_login(self.author)
        response = self.client.get(reverse('submission_edit', args=[self.sub_a.pk]), HTTP_HOST='localhost')
        self.assertEqual(response.status_code, 302)  # bounced back to detail
        response = self.client.post(
            reverse('submission_edit', args=[self.sub_a.pk]),
            {'title': 'Sneaky change', 'cover_letter': ''},
            HTTP_HOST='localhost',
        )
        self.sub_a.refresh_from_db()
        self.assertNotEqual(self.sub_a.title, 'Sneaky change')

    def test_only_owner_can_edit(self):
        self.sub_a.status = 'pending'; self.sub_a.save()
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('submission_edit', args=[self.sub_a.pk]), HTTP_HOST='localhost')
        self.assertEqual(response.status_code, 404)  # get_object_or_404(author=request.user)

    def test_bad_file_type_rejected(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        self.sub_a.status = 'pending'; self.sub_a.save()
        self.client.force_login(self.author)
        response = self.client.post(
            reverse('submission_edit', args=[self.sub_a.pk]),
            {'title': self.sub_a.title, 'cover_letter': '',
             'new_document': SimpleUploadedFile('bad.exe', b'x')},
            HTTP_HOST='localhost',
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Only Word documents')


class StatusesSectionRemovedTests(JournalRoleTestCase):

    def test_submission_list_has_no_status_filter(self):
        self.client.force_login(self.author)
        response = self.client.get(reverse('submission_list'), HTTP_HOST='localhost')
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'name="status"')  # the filter <select> is gone
        # ...but the passive per-row status pill remains
        self.assertContains(response, 'Paper in A')

    def test_author_dashboard_has_no_stat_tiles(self):
        self.client.force_login(self.author)
        response = self.client.get(reverse('author_dashboard'), HTTP_HOST='localhost')
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'uj-stat__value')
        self.assertNotIn('submission_stats', response.context)


class SubmitWordingTests(JournalRoleTestCase):

    def test_before_you_submit_tells_authors_to_keep_their_name(self):
        self.client.force_login(self.author)
        response = self.client.get(reverse('submission_create'), HTTP_HOST='localhost')
        self.assertContains(response, 'anonymise it automatically')
        self.assertNotContains(response, 'Remove any identifying information')


# ---------------------------------------------------------------------------
# Phase 4: review workflow + blind-review enforcement
# ---------------------------------------------------------------------------

from .models import ReviewRound, Assignment


class BlindReviewTests(JournalRoleTestCase):
    """The author's identity must never reach a blinded reviewer."""

    def setUp(self):
        super().setUp()
        self.reviewer = User.objects.create_user('rev@test.ng', 'pw12345!')
        self.reviewer.profile.is_reviewer = True
        self.reviewer.profile.save()
        # author has a real name so a leak would be visible
        self.author.first_name = 'Ada'; self.author.last_name = 'Lovelace'; self.author.save()

    def _assign(self, blinded=True):
        return Assignment.objects.create(
            submission=self.sub_a, assigned_to=self.reviewer,
            assigned_by=self.editor_a, role='reviewer', blinded=blinded,
        )

    def test_author_hidden_from_blinded_reviewer(self):
        self._assign(blinded=True)
        self.assertTrue(self.sub_a.is_author_hidden_from(self.reviewer))
        self.assertEqual(self.sub_a.author_label_for(self.reviewer), self.sub_a.anonymized_identifier)

    def test_author_visible_to_non_blinded_reviewer(self):
        self._assign(blinded=False)
        self.assertFalse(self.sub_a.is_author_hidden_from(self.reviewer))
        self.assertEqual(self.sub_a.author_label_for(self.reviewer), 'Ada Lovelace')

    def test_author_and_staff_always_see_identity(self):
        self.assertFalse(self.sub_a.is_author_hidden_from(self.author))
        self.assertFalse(self.sub_a.is_author_hidden_from(self.site_staff))
        self.assertFalse(self.sub_a.is_author_hidden_from(self.editor_a))  # journal team

    def test_unknown_viewer_hidden_by_default(self):
        self.assertTrue(self.sub_a.is_author_hidden_from(self.outsider))

    def test_work_page_never_shows_author_name(self):
        self._assign(blinded=True)
        self.sub_a.cover_letter = 'Submitted by Ada Lovelace of Cambridge'
        self.sub_a.save()
        self.client.force_login(self.reviewer)
        response = self.client.get(reverse('work_on_submission', args=[self.sub_a.pk]), HTTP_HOST='localhost')
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Ada Lovelace')          # name hidden
        self.assertNotContains(response, 'Cambridge')             # cover letter hidden
        self.assertContains(response, self.sub_a.anonymized_identifier)

    def test_reviewer_cannot_download_authors_original(self):
        self._assign(blinded=True)
        from django.core.files.uploadedfile import SimpleUploadedFile
        original = DocumentVersion.objects.create(
            submission=self.sub_a, uploaded_by=self.author,
            document=SimpleUploadedFile('orig.docx', b'x'), is_review_copy=False,
        )
        self.client.force_login(self.reviewer)
        response = self.client.get(reverse('download_document', args=[original.pk]), HTTP_HOST='localhost')
        self.assertEqual(response.status_code, 302)  # bounced, not served

    def test_reviewer_can_download_review_copy(self):
        self._assign(blinded=True)
        from django.core.files.uploadedfile import SimpleUploadedFile
        copy = DocumentVersion.objects.create(
            submission=self.sub_a, uploaded_by=self.editor_a,
            document=SimpleUploadedFile('copy.docx', b'x'), is_review_copy=True,
        )
        self.client.force_login(self.reviewer)
        response = self.client.get(reverse('download_document', args=[copy.pk]), HTTP_HOST='localhost')
        self.assertEqual(response.status_code, 200)


class PrepareAndAssignTests(JournalRoleTestCase):

    def setUp(self):
        super().setUp()
        self.reviewer = User.objects.create_user('rev2@test.ng', 'pw12345!')
        # Must be a valid choice in the assignment form's reviewer queryset.
        self.reviewer.profile.is_reviewer = True
        self.reviewer.profile.save()

    def test_cannot_assign_reviewer_without_review_copy(self):
        self.client.force_login(self.editor_a)
        response = self.client.post(
            reverse('assign_submission', args=[self.sub_a.pk]),
            {'assigned_to': self.reviewer.pk, 'role': 'reviewer', 'notes': ''},
            HTTP_HOST='localhost',
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(self.sub_a.assignments.filter(role='reviewer').exists())

    def test_prepare_review_copy_then_assign(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        self.client.force_login(self.editor_a)
        # prepare
        r = self.client.post(
            reverse('prepare_for_review', args=[self.sub_a.pk]),
            {'document': SimpleUploadedFile('deid.docx', b'x'), 'notes': ''},
            HTTP_HOST='localhost',
        )
        self.assertEqual(r.status_code, 302)
        self.sub_a.refresh_from_db()
        self.assertTrue(self.sub_a.has_review_copy)
        self.assertEqual(self.sub_a.status, 'preparing')
        self.assertIsNotNone(self.sub_a.current_round)  # round 1 opened
        # now assign
        r = self.client.post(
            reverse('assign_submission', args=[self.sub_a.pk]),
            {'assigned_to': self.reviewer.pk, 'role': 'reviewer', 'notes': ''},
            HTTP_HOST='localhost',
        )
        self.sub_a.refresh_from_db()
        assignment = self.sub_a.assignments.get(role='reviewer')
        self.assertEqual(self.sub_a.status, 'in_review')
        self.assertEqual(assignment.review_round, self.sub_a.current_round)

    def test_reopen_review_opens_next_round(self):
        self.sub_a.status = 'revised'; self.sub_a.save()
        self.sub_a.open_new_round(opened_by=self.editor_a)  # round 1
        self.client.force_login(self.editor_a)
        response = self.client.post(reverse('reopen_review', args=[self.sub_a.pk]), HTTP_HOST='localhost')
        self.assertEqual(response.status_code, 302)
        self.sub_a.refresh_from_db()
        self.assertEqual(self.sub_a.current_round.number, 2)
        self.assertEqual(self.sub_a.status, 'preparing')


class RejectEmailTests(JournalRoleTestCase):

    def test_rejection_sends_email_to_author(self):
        from django.core import mail
        self.client.force_login(self.editor_a)
        response = self.client.post(
            reverse('reject_submission', args=[self.sub_a.pk]),
            {'reason': 'Out of scope'}, HTTP_HOST='localhost',
        )
        self.assertEqual(response.status_code, 302)
        self.sub_a.refresh_from_db()
        self.assertEqual(self.sub_a.status, 'rejected')
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(self.author.email, mail.outbox[0].to)


# ---------------------------------------------------------------------------
# Phase 5: volunteer reviewer portal
# ---------------------------------------------------------------------------

from .models import ReviewerApplication, GuestReviewer, Profile


class ReviewerApplyTests(JournalRoleTestCase):

    def _payload(self, **over):
        data = {
            'first_name': 'Grace', 'last_name': 'Hopper',
            'email': 'grace@navy.mil', 'affiliation': 'US Navy',
            'position': 'Rear Admiral', 'qualifications': 'PhD Mathematics',
            'expertise_areas': 'Compilers, Programming Languages',
            'statement': 'Happy to help.', 'website': '',
        }
        data.update(over)
        return data

    def test_public_can_apply_without_login(self):
        response = self.client.post(reverse('reviewer_apply'), self._payload(), HTTP_HOST='localhost')
        self.assertRedirects(response, reverse('reviewer_apply_thanks'), fetch_redirect_response=False)
        self.assertTrue(ReviewerApplication.objects.filter(email='grace@navy.mil', status='pending').exists())

    def test_confirmation_email_sent(self):
        from django.core import mail
        self.client.post(reverse('reviewer_apply'), self._payload(), HTTP_HOST='localhost')
        # confirmation to applicant is at least one of the sent emails
        recipients = [addr for m in mail.outbox for addr in m.to]
        self.assertIn('grace@navy.mil', recipients)

    def test_honeypot_blocks_bots(self):
        response = self.client.post(reverse('reviewer_apply'), self._payload(website='http://spam'), HTTP_HOST='localhost')
        self.assertEqual(response.status_code, 200)  # re-render, not redirect
        self.assertFalse(ReviewerApplication.objects.filter(email='grace@navy.mil').exists())

    def test_duplicate_pending_application_blocked(self):
        ReviewerApplication.objects.create(first_name='G', last_name='H', email='grace@navy.mil')
        response = self.client.post(reverse('reviewer_apply'), self._payload(), HTTP_HOST='localhost')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'already have an application')

    def test_apply_page_reachable(self):
        response = self.client.get(reverse('reviewer_apply'), HTTP_HOST='localhost')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Volunteer as a peer reviewer')


class ReviewerApplicationManagementTests(JournalRoleTestCase):

    def setUp(self):
        super().setUp()
        self.application = ReviewerApplication.objects.create(
            first_name='Grace', last_name='Hopper', email='grace@navy.mil',
            affiliation='US Navy', expertise_areas='Compilers',
        )

    def test_list_requires_editorial_role(self):
        self.client.force_login(self.outsider)
        r = self.client.get(reverse('reviewer_applications_list'), HTTP_HOST='localhost')
        self.assertEqual(r.status_code, 403)

    def test_editor_can_view_applications(self):
        self.client.force_login(self.editor_a)
        r = self.client.get(reverse('reviewer_applications_list'), HTTP_HOST='localhost')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Grace Hopper')

    def test_approve_as_user_creates_reviewer_account(self):
        self.client.force_login(self.editor_a)
        r = self.client.post(
            reverse('reviewer_application_decide', args=[self.application.pk]),
            {'decision': 'approve_user', 'notes': 'Welcome'},
            HTTP_HOST='localhost',
        )
        self.assertEqual(r.status_code, 302)
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, 'approved')
        user = User.objects.get(email='grace@navy.mil')
        self.assertTrue(user.profile.is_reviewer)
        self.assertEqual(self.application.created_user, user)
        self.assertFalse(user.has_usable_password())  # set-password link flow

    def test_approve_existing_user_flags_reviewer(self):
        existing = User.objects.create_user('grace@navy.mil', 'pw12345!')
        self.client.force_login(self.editor_a)
        self.client.post(
            reverse('reviewer_application_decide', args=[self.application.pk]),
            {'decision': 'approve_user', 'notes': ''}, HTTP_HOST='localhost',
        )
        existing.refresh_from_db()
        self.assertTrue(existing.profile.is_reviewer)
        self.assertTrue(existing.has_usable_password())  # unchanged

    def test_approve_as_guest_creates_guest_reviewer(self):
        self.client.force_login(self.editor_a)
        self.client.post(
            reverse('reviewer_application_decide', args=[self.application.pk]),
            {'decision': 'approve_guest', 'notes': ''}, HTTP_HOST='localhost',
        )
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, 'approved')
        self.assertIsNotNone(self.application.guest_reviewer)
        self.assertTrue(GuestReviewer.objects.filter(email='grace@navy.mil').exists())

    def test_reject_notifies_applicant(self):
        from django.core import mail
        self.client.force_login(self.editor_a)
        self.client.post(
            reverse('reviewer_application_decide', args=[self.application.pk]),
            {'decision': 'reject', 'notes': 'Not this time'}, HTTP_HOST='localhost',
        )
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, 'rejected')
        recipients = [addr for m in mail.outbox for addr in m.to]
        self.assertIn('grace@navy.mil', recipients)

    def test_cannot_decide_twice(self):
        self.application.status = 'approved'; self.application.save()
        self.client.force_login(self.editor_a)
        r = self.client.post(
            reverse('reviewer_application_decide', args=[self.application.pk]),
            {'decision': 'reject', 'notes': ''}, HTTP_HOST='localhost',
        )
        self.assertEqual(r.status_code, 302)
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, 'approved')  # unchanged


# ---------------------------------------------------------------------------
# Phase 6b: publication fees + Paystack payments
# ---------------------------------------------------------------------------

import hashlib
import hmac
import json
from unittest import mock

from django.test import override_settings
from .models import JournalFee, Payment
from . import paystack


class PublicationFeeGateTests(JournalRoleTestCase):
    """A journal fee holds an accepted article at awaiting_payment."""

    def setUp(self):
        super().setUp()
        JournalFee.objects.create(journal=self.journal_a, amount=5000, currency='NGN', is_active=True)
        self.sub_a.status = 'approved'
        self.sub_a.save()

    def test_requires_payment_when_fee_active(self):
        self.assertIsNotNone(self.sub_a.active_fee)
        self.assertTrue(self.sub_a.requires_payment)
        self.assertFalse(self.sub_a.is_paid)

    def test_no_fee_journal_never_requires_payment(self):
        self.sub_b.status = 'approved'; self.sub_b.save()
        self.assertFalse(self.sub_b.requires_payment)

    def test_publish_blocked_and_author_notified(self):
        from django.core import mail
        self.client.force_login(self.editor_a)
        response = self.client.post(reverse('publish_submission', args=[self.sub_a.pk]),
                                    {'title': 'X'}, HTTP_HOST='localhost')
        self.assertEqual(response.status_code, 302)
        self.sub_a.refresh_from_db()
        self.assertEqual(self.sub_a.status, 'awaiting_payment')
        self.assertTrue(self.sub_a.payments.filter(status='pending').exists())
        self.assertIn(self.author.email, [a for m in mail.outbox for a in m.to])

    def test_request_payment_action(self):
        self.client.force_login(self.editor_a)
        r = self.client.post(reverse('request_payment', args=[self.sub_a.pk]), HTTP_HOST='localhost')
        self.assertEqual(r.status_code, 302)
        self.sub_a.refresh_from_db()
        self.assertEqual(self.sub_a.status, 'awaiting_payment')

    def test_waive_clears_the_gate(self):
        self.client.force_login(self.editor_a)
        self.client.post(reverse('waive_payment', args=[self.sub_a.pk]),
                         {'reason': 'Student'}, HTTP_HOST='localhost')
        self.sub_a.refresh_from_db()
        self.assertTrue(self.sub_a.is_paid)
        self.assertFalse(self.sub_a.requires_payment)
        self.assertEqual(self.sub_a.status, 'approved')  # gate lifted
        payment = self.sub_a.payments.get()
        self.assertEqual(payment.status, 'waived')
        self.assertEqual(payment.waived_by, self.editor_a)

    def test_only_chief_editor_can_waive(self):
        plain = User.objects.create_user('ed3@test.ng', 'pw12345!')
        JournalRole.objects.create(user=plain, journal=self.journal_a, role=JournalRole.ROLE_EDITOR)
        self.client.force_login(plain)
        r = self.client.post(reverse('waive_payment', args=[self.sub_a.pk]), {'reason': ''}, HTTP_HOST='localhost')
        self.assertEqual(r.status_code, 403)


@override_settings(PAYSTACK_SECRET_KEY='sk_test_dummy', PAYSTACK_PUBLIC_KEY='pk_test_dummy')
class PaymentFlowTests(JournalRoleTestCase):

    def setUp(self):
        super().setUp()
        JournalFee.objects.create(journal=self.journal_a, amount=5000, currency='NGN', is_active=True)
        self.sub_a.status = 'awaiting_payment'; self.sub_a.save()
        self.payment = Payment.objects.create(
            submission=self.sub_a, author=self.author, amount=5000,
            currency='NGN', reference='UJ-testref-001',
        )

    def test_pay_redirects_to_paystack(self):
        with mock.patch.object(paystack, 'initialize_transaction',
                               return_value={'authorization_url': 'https://paystack.test/redir'}):
            self.client.force_login(self.author)
            r = self.client.post(reverse('pay_submission', args=[self.sub_a.pk]), HTTP_HOST='localhost')
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r['Location'], 'https://paystack.test/redir')

    def test_callback_marks_paid_on_success(self):
        with mock.patch.object(paystack, 'verify_transaction',
                               return_value={'status': 'success', 'reference': 'UJ-testref-001'}):
            self.client.force_login(self.author)
            r = self.client.get(reverse('paystack_callback'),
                                 {'reference': 'UJ-testref-001'}, HTTP_HOST='localhost')
        self.assertEqual(r.status_code, 302)
        self.payment.refresh_from_db(); self.sub_a.refresh_from_db()
        self.assertEqual(self.payment.status, 'success')
        self.assertEqual(self.sub_a.status, 'approved')  # cleared for publishing

    def test_webhook_valid_signature_marks_paid(self):
        body = json.dumps({'event': 'charge.success', 'data': {'reference': 'UJ-testref-001'}}).encode()
        sig = hmac.new(b'sk_test_dummy', body, hashlib.sha512).hexdigest()
        r = self.client.post(reverse('paystack_webhook'), data=body,
                             content_type='application/json',
                             HTTP_X_PAYSTACK_SIGNATURE=sig, HTTP_HOST='localhost')
        self.assertEqual(r.status_code, 200)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, 'success')

    def test_webhook_bad_signature_rejected(self):
        body = json.dumps({'event': 'charge.success', 'data': {'reference': 'UJ-testref-001'}}).encode()
        r = self.client.post(reverse('paystack_webhook'), data=body,
                             content_type='application/json',
                             HTTP_X_PAYSTACK_SIGNATURE='wrong', HTTP_HOST='localhost')
        self.assertEqual(r.status_code, 400)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, 'pending')  # untouched

    def test_webhook_is_idempotent(self):
        body = json.dumps({'event': 'charge.success', 'data': {'reference': 'UJ-testref-001'}}).encode()
        sig = hmac.new(b'sk_test_dummy', body, hashlib.sha512).hexdigest()
        for _ in range(2):
            self.client.post(reverse('paystack_webhook'), data=body,
                             content_type='application/json',
                             HTTP_X_PAYSTACK_SIGNATURE=sig, HTTP_HOST='localhost')
        self.assertEqual(Payment.objects.filter(reference='UJ-testref-001', status='success').count(), 1)

    def test_signature_helper(self):
        body = b'{"x":1}'
        good = hmac.new(b'sk_test_dummy', body, hashlib.sha512).hexdigest()
        self.assertTrue(paystack.verify_webhook_signature(body, good))
        self.assertFalse(paystack.verify_webhook_signature(body, 'nope'))


class PaymentUnconfiguredTests(JournalRoleTestCase):

    @override_settings(PAYSTACK_SECRET_KEY='')
    def test_pay_fails_gracefully_without_keys(self):
        JournalFee.objects.create(journal=self.journal_a, amount=5000, is_active=True)
        self.sub_a.status = 'awaiting_payment'; self.sub_a.save()
        Payment.objects.create(submission=self.sub_a, author=self.author,
                               amount=5000, currency='NGN', reference='UJ-x')
        self.client.force_login(self.author)
        r = self.client.post(reverse('pay_submission', args=[self.sub_a.pk]), HTTP_HOST='localhost')
        self.assertEqual(r.status_code, 302)  # redirected back with an error message, no crash


# ---------------------------------------------------------------------------
# Multi-journal portal: issues, editorial board, and per-journal pages
# ---------------------------------------------------------------------------

import datetime

from .models import Article, EditorialBoardMember, Issue, JournalPage


class JournalIssueTests(JournalRoleTestCase):
    """Editions belong to one journal and never leak into another's archive."""

    def setUp(self):
        super().setUp()
        self.issue_a = Issue.objects.create(
            journal=self.journal_a, volume='2', number='1', year=2026,
            published_date=datetime.date(2026, 3, 1),
        )
        self.issue_b = Issue.objects.create(
            journal=self.journal_b, volume='2', number='1', year=2026,
            published_date=datetime.date(2026, 3, 1),
        )

    def test_label_reads_as_the_client_writes_it(self):
        self.assertEqual(self.issue_a.label, 'Volume 2(1) 2026')

    def test_volume_and_number_are_unique_per_journal_not_globally(self):
        # Both journals may have a Volume 2(1) — that is the whole point of
        # keying editions on the journal rather than the department.
        self.assertEqual(Issue.objects.filter(volume='2', number='1').count(), 2)

    def test_issues_are_listed_newest_first_despite_annotation(self):
        # Same trap as the home page: annotate() groups the query and Django
        # drops Meta.ordering, but the year grouping depends on sort order.
        older = Issue.objects.create(
            journal=self.journal_a, volume='1', number='1', year=2024,
            published_date=datetime.date(2024, 1, 1),
        )
        newer = Issue.objects.create(
            journal=self.journal_a, volume='3', number='1', year=2027,
            published_date=datetime.date(2027, 1, 1),
        )
        response = self.client.get(
            reverse('journal_issues', args=[self.journal_a.slug]), HTTP_HOST='localhost')
        self.assertEqual(
            [g['year'] for g in response.context['issue_years']], [2027, 2026, 2024])
        flat = [i for g in response.context['issue_years'] for i in g['issues']]
        self.assertEqual(flat, [newer, self.issue_a, older])

    def test_issue_list_shows_only_this_journals_editions(self):
        response = self.client.get(
            reverse('journal_issues', args=[self.journal_a.slug]), HTTP_HOST='localhost')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context['issue_years'][0]['issues']), [self.issue_a])

    def test_unpublished_issue_is_hidden_from_readers(self):
        self.issue_a.is_published = False
        self.issue_a.save(update_fields=['is_published'])

        listing = self.client.get(
            reverse('journal_issues', args=[self.journal_a.slug]), HTTP_HOST='localhost')
        self.assertEqual(listing.context['issue_count'], 0)

        detail = self.client.get(
            reverse('issue_detail', args=[self.journal_a.slug, self.issue_a.pk]),
            HTTP_HOST='localhost')
        self.assertEqual(detail.status_code, 404)

    def test_an_issue_cannot_be_read_through_another_journals_url(self):
        response = self.client.get(
            reverse('issue_detail', args=[self.journal_b.slug, self.issue_a.pk]),
            HTTP_HOST='localhost')
        self.assertEqual(response.status_code, 404)

    def test_issue_detail_lists_only_published_articles(self):
        published = Article.objects.create(
            title='Published paper', abstract='a', content='c',
            author=self.author, journal=self.journal_a, issue=self.issue_a,
            status='published',
        )
        Article.objects.create(
            title='Draft paper', abstract='a', content='c',
            author=self.author, journal=self.journal_a, issue=self.issue_a,
            status='draft',
        )
        response = self.client.get(
            reverse('issue_detail', args=[self.journal_a.slug, self.issue_a.pk]),
            HTTP_HOST='localhost')
        self.assertEqual(list(response.context['articles']), [published])


class JournalBoardAndPageTests(JournalRoleTestCase):
    """The public editorial board and policy pages are per-journal."""

    def test_board_is_grouped_by_section_and_hides_inactive_people(self):
        EditorialBoardMember.objects.create(
            journal=self.journal_a, name='Prof. Ada Eze', position='Editor-in-Chief',
            section=EditorialBoardMember.SECTION_BOARD,
        )
        EditorialBoardMember.objects.create(
            journal=self.journal_a, name='Dr. Bala Musa', position='Consultant',
            section=EditorialBoardMember.SECTION_CONSULTANTS,
        )
        EditorialBoardMember.objects.create(
            journal=self.journal_a, name='Retired Person', position='Former editor',
            is_active=False,
        )
        EditorialBoardMember.objects.create(
            journal=self.journal_b, name='Other Journal Editor', position='Editor',
        )

        response = self.client.get(
            reverse('journal_board', args=[self.journal_a.slug]), HTTP_HOST='localhost')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [s['label'] for s in response.context['sections']],
            ['Editorial Board', 'Editorial Consultants'],
        )
        self.assertContains(response, 'Prof. Ada Eze')
        self.assertNotContains(response, 'Retired Person')
        self.assertNotContains(response, 'Other Journal Editor')

    def test_a_page_is_reachable_only_under_its_own_journal(self):
        JournalPage.objects.create(
            journal=self.journal_a, title='Review Policy', slug='review-policy',
            content='<p>Double blind.</p>',
        )
        ours = self.client.get(
            reverse('journal_page', args=[self.journal_a.slug, 'review-policy']),
            HTTP_HOST='localhost')
        self.assertContains(ours, 'Double blind.')

        theirs = self.client.get(
            reverse('journal_page', args=[self.journal_b.slug, 'review-policy']),
            HTTP_HOST='localhost')
        self.assertEqual(theirs.status_code, 404)

    def test_unpublished_page_is_hidden_and_kept_out_of_the_nav(self):
        JournalPage.objects.create(
            journal=self.journal_a, title='Draft Policy', slug='draft-policy',
            content='<p>Not ready.</p>', is_published=False,
        )
        response = self.client.get(
            reverse('journal_page', args=[self.journal_a.slug, 'draft-policy']),
            HTTP_HOST='localhost')
        self.assertEqual(response.status_code, 404)
        self.assertNotIn('draft-policy', [p.slug for p in self.journal_a.nav_pages])


class JournalManagementAccessTests(JournalRoleTestCase):
    """The new management screens honour the same per-journal boundary."""

    MANAGE_VIEWS = (
        'journal_settings', 'journal_issues_manage',
        'journal_board_manage', 'journal_pages_manage',
    )

    def test_chief_editor_reaches_only_their_own_journal(self):
        self.client.force_login(self.editor_a)
        for name in self.MANAGE_VIEWS:
            with self.subTest(view=name):
                mine = self.client.get(
                    reverse(name, args=[self.journal_a.pk]), HTTP_HOST='localhost')
                self.assertEqual(mine.status_code, 200)

                theirs = self.client.get(
                    reverse(name, args=[self.journal_b.pk]), HTTP_HOST='localhost')
                self.assertEqual(theirs.status_code, 403)

    def test_author_cannot_reach_any_management_screen(self):
        self.client.force_login(self.author)
        for name in self.MANAGE_VIEWS:
            with self.subTest(view=name):
                response = self.client.get(
                    reverse(name, args=[self.journal_a.pk]), HTTP_HOST='localhost')
                self.assertEqual(response.status_code, 403)

    def test_editor_can_add_an_issue_to_their_journal(self):
        self.client.force_login(self.editor_a)
        response = self.client.post(
            reverse('journal_issues_manage', args=[self.journal_a.pk]),
            {
                'volume': '3', 'number': '2', 'year': '2026',
                'title': '', 'description': '',
                'published_date': '2026-06-01', 'is_published': 'on',
            },
            HTTP_HOST='localhost',
        )
        self.assertEqual(response.status_code, 302)
        issue = Issue.objects.get(journal=self.journal_a, volume='3', number='2')
        self.assertEqual(issue.uploaded_by, self.editor_a)

    def test_duplicate_volume_is_reported_not_crashed(self):
        Issue.objects.create(
            journal=self.journal_a, volume='3', number='2', year=2026,
            published_date=datetime.date(2026, 6, 1),
        )
        self.client.force_login(self.editor_a)
        response = self.client.post(
            reverse('journal_issues_manage', args=[self.journal_a.pk]),
            {
                'volume': '3', 'number': '2', 'year': '2026',
                'title': '', 'description': '',
                'published_date': '2026-06-01', 'is_published': 'on',
            },
            HTTP_HOST='localhost',
        )
        # Re-renders the form with an error rather than raising IntegrityError.
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'already has an issue')
        self.assertEqual(Issue.objects.filter(journal=self.journal_a).count(), 1)

    def test_an_issue_holding_articles_is_not_deleted(self):
        issue = Issue.objects.create(
            journal=self.journal_a, volume='4', number='1', year=2026,
            published_date=datetime.date(2026, 9, 1),
        )
        Article.objects.create(
            title='Keeper', abstract='a', content='c', author=self.author,
            journal=self.journal_a, issue=issue, status='published',
        )
        self.client.force_login(self.editor_a)
        self.client.post(
            reverse('issue_delete', args=[self.journal_a.pk, issue.pk]),
            HTTP_HOST='localhost')
        self.assertTrue(Issue.objects.filter(pk=issue.pk).exists())


class JournalSeedDataTests(TestCase):
    """The three journals the client actually runs exist after migration."""

    def test_the_three_journals_are_seeded_with_slugs(self):
        expected = {
            'jjel': 'Jos Journal of the English Language',
            'jojwol': 'Jos Journal of Written and Oral Literature',
            'humanity': 'Humanity Journal',
        }
        for slug, name in expected.items():
            with self.subTest(slug=slug):
                journal = Journal.objects.get(slug=slug)
                self.assertEqual(journal.name, name)
                self.assertTrue(journal.is_active)

    def test_home_page_leads_with_the_journals_in_order(self):
        # Regression: the home queryset annotates counts, and Django drops
        # Meta.ordering from a grouped query — so without an explicit order_by
        # the cards came back in arbitrary database order. Shuffling the `order`
        # values proves the view is really sorting rather than getting lucky.
        Journal.objects.filter(slug='humanity').update(order=1)
        Journal.objects.filter(slug='jjel').update(order=3)

        response = self.client.get(reverse('home'), HTTP_HOST='localhost')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [j.slug for j in response.context['journals']],
            ['humanity', 'jojwol', 'jjel'],
        )

    def test_journal_list_page_honours_the_same_order(self):
        response = self.client.get(reverse('journal_list'), HTTP_HOST='localhost')
        self.assertEqual(
            [j.slug for j in response.context['journals']],
            ['jjel', 'jojwol', 'humanity'],
        )


class EditorialBoardInitialsTests(TestCase):
    """Avatar initials skip the honorific, or a whole board reads 'P, P, D, D'."""

    def _initials(self, name):
        return EditorialBoardMember(name=name).initials

    def test_honorific_is_ignored(self):
        self.assertEqual(self._initials('Prof. Ada N. Eze'), 'AE')
        self.assertEqual(self._initials('Dr. Bala Musa'), 'BM')
        self.assertEqual(self._initials('Mrs Ngozi Okafor'), 'NO')

    def test_plain_names_still_work(self):
        self.assertEqual(self._initials('Ada Eze'), 'AE')
        self.assertEqual(self._initials('Ada'), 'A')

    def test_degenerate_names_do_not_crash(self):
        self.assertEqual(self._initials('Prof.'), 'P')
        self.assertEqual(self._initials('   '), '?')
