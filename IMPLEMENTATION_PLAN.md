# Client Feedback — Implementation Plan

Status: **proposed**. Nothing below is built yet.

Scope: the ten items from client feedback, mapped onto the current codebase.
Ordered so that the things everything else depends on (the per-journal role model)
land first, and the two genuinely large items (house-style publishing, payments)
land last.

---

## 0. What already exists (and what that changes)

Worth reading first — four of the ten items are partly built, and one is a
one-line fix, not a feature.

| Feedback item | Current state |
|---|---|
| Rubrics per journal | **Model already exists.** `Rubric(journal, title, content, order)` — `models.py:167`. Registered in Django admin, rendered on `article_form.html:50`. Missing: front-end editing, and it isn't shown on the journal page. |
| Per-journal admin role | **Nothing.** `Profile.is_editor` / `is_reviewer` are global booleans; every admin view is `@staff_member_required` (site-wide staff). This is the biggest structural gap. |
| Per-journal checklist | **Nothing.** No model, no UI. |
| Remove statuses section | **Trivial.** Status filter dropdown at `submissions/submission_list.html:16-27`; 9-key `submission_stats` dict at `views.py:242`. |
| Volunteer reviewer portal | **Half.** `GuestReviewer` model + invite/token/email flow exists (`submission_views.py:1198-1341`). Missing: the public *apply* side. |
| Author edits own submission | **Partly.** `submission_revise` exists but is hard-gated to `status == 'revision_requested'` (`submission_views.py:244`). `DocumentVersion` gives us free version history. |
| "Before you submit" wording | **One bullet to delete** — `submissions/submission_form.html:103`. |
| Blind review = code not name | **Mostly built.** `Submission.anonymized_identifier` (`MS-YYYY-####`), `Assignment.blinded`, and `sanitize_document_metadata()` strips docx author metadata on download. **But there is a live leak** — see 6.1. |
| Editor↔reviewer↔author loop | **Partly.** `assign_submission`, `Assignment.amended_document`, `share_with_author`, `request_revision`, `approve_submission`, `publish_submission` all exist. Missing: the editor's "prepare for review" step, round tracking, and re-assignment after a revision. |
| House publishing format | **Weak.** `extract_document_content()` (`submission_views.py:58`) is a heuristic paragraph scraper — it guesses the title from the first bold/heading paragraph and switches sections on exact-match keywords like `abstract`/`references`. Output goes into `Article.extracted_sections` (JSON) and is rendered ad hoc. |
| Paystack payment | **Nothing.** No payment model, no keys, no dependency. |

---

## Phase 1 — Per-journal roles (foundation)

Everything in Phases 2–4 depends on answering "who is allowed to edit *this*
journal's rubrics / manage *this* journal's submissions", so this goes first.

### 1.1 Model

New model in `journalapp/models.py`:

```python
class JournalRole(models.Model):
    ROLE_CHOICES = (
        ('admin',        'Journal Admin'),      # manages rubrics, checklist, settings
        ('chief_editor', 'Chief Editor'),       # runs the review workflow, publishes
        ('editor',       'Editor'),             # assists; cannot publish
    )
    user    = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='journal_roles', ...)
    journal = models.ForeignKey(Journal, related_name='roles', ...)
    role    = models.CharField(max_length=20, choices=ROLE_CHOICES)
    granted_by = models.ForeignKey(..., null=True)
    granted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'journal', 'role')
```

`Profile.is_editor` / `is_reviewer` stay untouched — legacy views still read
them, and removing them is a separate cleanup.

### 1.2 Permission helpers

New `journalapp/permissions.py`:

- `has_journal_role(user, journal, roles=None) -> bool` — site superusers/staff
  return `True` for everything, so nothing existing breaks.
- `journals_for(user, roles=None) -> QuerySet[Journal]`
- `@journal_staff_required(roles=(...))` decorator, resolving the journal from
  `pk`/`journal_id`/`submission.journal` depending on the view.

### 1.3 Scope the existing admin views

`admin_submission_list`, `admin_submission_detail`, `assign_submission`,
`request_revision`, `upload_final_document`, `preview_extracted_content`,
`publish_submission`, `reject_submission`, `approve_submission`,
`share_with_author` — swap `@staff_member_required` for
`@journal_staff_required(...)` and filter querysets by `journals_for(request.user)`.

Site superusers keep seeing everything, so this is behaviour-preserving for the
current single-admin setup.

### 1.4 UI

- Django admin: `JournalRoleInline` on `JournalAdmin` + a standalone `JournalRoleAdmin`.
- Front-end: `manage/journals/<pk>/team/` — grant/revoke roles. Visible to
  journal admins and superusers.

**Migration:** additive only. One data migration is worth writing — grant
`chief_editor` on every journal to each existing `is_staff` user, so nobody
loses access on deploy day.

---

## Phase 2 — Journal content: rubrics + checklist

### 2.1 Rubrics front-end (item 1)

The model exists; this is CRUD + surfacing.

- Views: `journal_rubrics` (list), `rubric_create`, `rubric_update`,
  `rubric_delete` — all `@journal_staff_required(roles=('admin','chief_editor'))`.
- URLs under `manage/journals/<journal_id>/rubrics/`.
- `RubricForm` with CKEditor for `content`, drag-or-number ordering.
- **Surface it publicly**: add a "Review rubrics" section to the journal page.
  Note `department_journal` (`views.py:569`) is keyed on *department*, not
  journal, so this needs a real per-journal public page — see 2.3.

### 2.2 Submission checklist (item 3)

New models:

```python
class ChecklistItem(models.Model):
    journal   = models.ForeignKey(Journal, related_name='checklist_items', ...)
    text      = models.CharField(max_length=500)
    help_text = models.CharField(max_length=500, blank=True)
    order     = models.PositiveIntegerField(default=0)
    required  = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)

class ChecklistResponse(models.Model):
    submission = models.ForeignKey(Submission, related_name='checklist_responses', ...)
    item       = models.ForeignKey(ChecklistItem, on_delete=models.PROTECT)
    item_text  = models.CharField(max_length=500)   # frozen copy — items get edited later
    checked    = models.BooleanField(default=False)
    responded_at = models.DateTimeField(auto_now_add=True)
```

`item_text` is denormalised on purpose: a checklist item reworded in 2027 must
not silently rewrite what an author agreed to in 2026.

- Same CRUD pattern + permissions as rubrics.
- Rendered on the journal page (read-only, "what you'll be asked to confirm").
- Rendered as real checkboxes in `submissions/submission_form.html`, built
  dynamically from the selected journal. Server-side validation in
  `submission_create` rejects the POST if any `required` item is unticked —
  client-side only is not enough.
- Shown to the chief editor on `admin_submission_detail`.

### 2.3 A real journal page

`department_journal` is department-scoped and `JournalListView` has no detail
view — there is currently **no per-journal public page** to hang rubrics and the
checklist on. Add `journals/<pk>/` → `journal_detail.html`: description, cover,
rubrics, checklist, published articles, "Submit to this journal" CTA.

---

## Phase 3 — Author experience

### 3.1 Remove the statuses section (item 4)

Interpreting "they do not need to check on a status dropdown" as the *filter
control* and the stats grid, not the per-row status pill (the pill is passive —
it's how an author sees where things stand at a glance, which is what the client
wants preserved).

- Delete the status `<select>` form, `submissions/submission_list.html:16-27`.
- Drop `status_filter` / `status_choices` from `submission_list` (`submission_views.py:188`).
- Drop the `submission_stats` status tiles from `author_dashboard`
  (`views.py:242-252`) and the template block that renders them. Keep `total`.
- Make the timeline the primary tracker: promote `SubmissionLog` on
  `submission_detail.html` into a proper `.uj-timeline` (the CSS already exists),
  and make sure every state change writes a human-readable
  `log_submission_action(...)` entry.

> ⚠️ Confirm before building: if the client meant "remove the Status *column*
> too", say so — it's a smaller change, but it removes at-a-glance tracking.

### 3.2 Author can edit / re-upload until accepted (item 6)

Currently blocked: `submission_revise` returns an error unless
`status == 'revision_requested'` (`submission_views.py:244`).

- Add `Submission.is_editable_by_author` →
  `status in ('pending', 'revision_requested', 'revised')`, i.e. anything before
  `in_review` locks it, and `approved`/`published`/`rejected` are final.
  (`in_review` is deliberately *not* editable — swapping the file under a
  reviewer mid-read is worse than making them ask for it back.)
- New `submission_edit` view: title, cover letter, **and** replace the document.
- Re-uploading writes a **new `DocumentVersion`** rather than overwriting —
  the client's "so that they do not have to upload multiple different files" is
  about the author's experience (one live document, not a pile of attachments);
  history still matters for the editor.
- Every edit logs to `SubmissionLog`. Edit + Delete-draft buttons on
  `submission_detail.html`, gated on the property.

### 3.3 "Before you submit" (item 7)

Delete the bullet *"Remove any identifying information for blind peer review"*
(`submissions/submission_form.html:103`) and replace with something like *"Keep
your name and affiliation in the document — we anonymise it automatically before
reviewers see it."* That claim is already true: `sanitize_document_metadata()`
strips docx core properties on blinded download (`submission_views.py:1047`).

> Caveat to raise with the client: metadata stripping does **not** remove a name
> typed on the title page or a self-citation in the body. If authors keep
> identifying info, the chief editor's "prepare for review" step (4.1) is what
> actually makes the manuscript blind. Phase 4 is therefore a prerequisite for
> this being honest, not just a wording change.

---

## Phase 4 — Review workflow (items 8 + 9)

### 4.1 The process the client described

> Author submits → Chief editor downloads and prepares it for review → sends to
> reviewer → reviewer downloads, comments, uploads back → chief editor returns it
> to the author → author corrects and re-uploads → loop → chief editor publishes.

Mapping to current code, the gaps are:

1. **No "prepare for review" step.** Add `prepare_for_review` — the chief editor
   uploads a review-ready (de-identified, formatted) copy as a `DocumentVersion`
   flagged `is_review_copy=True`; that version, not the author's original, is what
   reviewers download. New status `preparing`.
2. **No round tracking.** Add `ReviewRound(submission, number, opened_at, closed_at, outcome)`
   and FK `Assignment.round`. Without it, round 2 assignments are
   indistinguishable from round 1 in the log.
3. **No loop-back.** After `submission_revise` sets `revised`, nothing re-opens a
   round. Add "Send back to reviewers" on `admin_submission_detail` → opens round
   N+1 and re-assigns (same reviewers by default).
4. **Rejection email is a `TODO`** (`submission_views.py:692`). Wire it up with
   the existing `get_from_email()` helper.

Status machine after this phase:

```
pending → preparing → in_review → with_editor → revision_requested
   ↑                                   ↓              ↓
   └───────── (round N+1) ───────── revised ──────────┘
                                       ↓
                                   approved → awaiting_payment → published
                                       ↓
                                    rejected
```

`awaiting_payment` comes from Phase 6; add the field now, gate on it later.

### 4.2 Close the blind-review leak (item 8)

`Submission.anonymized_identifier` already exists and is already displayed.
The problems are enforcement, not identifiers:

- **Live leak:** `submissions/my_assignments.html:27` renders
  `assignment.submission.author.get_full_name` — it *is* inside an
  `{% if assignment.blinded %}…{% else %}` branch, so it only fires on
  non-blinded assignments, but the same pattern is repeated across four
  templates and one wrong `{% else %}` re-exposes the author. Fix by inverting
  the responsibility.
- **Move blinding server-side.** Add `Submission.public_label_for(user)` →
  returns `anonymized_identifier` when the viewer is a blinded assignee, real
  title/author otherwise. Templates call one accessor instead of each
  re-implementing the `{% if blinded %}` test.
- **Chat.** `work_on_submission.html:81` masks the author's name in messages —
  good — but `send_message` does not stop a reviewer from *reading* an
  attachment filename containing the author's name. Sanitise attachment names on
  blinded threads.
- **Reviewer-visible downloads** already route through
  `sanitize_document_metadata()`; extend the same guard to `guest_download_document`
  for the review-copy path introduced in 4.1.
- Add regression tests: a blinded reviewer requesting every reviewer-reachable
  URL must never receive the author's name or email in the response body.

---

## Phase 5 — Volunteer peer reviewer portal (item 5)

### 5.1 Public application

New model:

```python
class ReviewerApplication(models.Model):
    STATUS = (('pending','Pending'), ('approved','Approved'), ('rejected','Rejected'))
    first_name, last_name, email, affiliation, position
    qualifications   = models.TextField()          # degrees, publications
    expertise_areas  = models.TextField()          # comma-separated, matches GuestReviewer
    journals_of_interest = models.ManyToManyField(Journal, blank=True)
    cv               = models.FileField(upload_to='reviewer_cvs/', blank=True)
    statement        = models.TextField(blank=True)
    status           = models.CharField(choices=STATUS, default='pending')
    reviewed_by, reviewed_at, review_notes
    created_user     = models.OneToOneField(CustomUser, null=True, blank=True)
    guest_reviewer   = models.OneToOneField(GuestReviewer, null=True, blank=True)
```

- Public page `reviewers/apply/` — no login. Honeypot + rate limit; this is an
  unauthenticated public form on a live domain.
- Confirmation email to applicant, notification to journal admins.

### 5.2 Management

- `manage/reviewer-applications/` — list, filter by status/journal/expertise,
  detail view, approve/reject with notes.
- **Approve** does one of two things, chosen by the reviewing admin:
  - create a `CustomUser` + `Profile.is_reviewer=True` (they get a login), or
  - create a `GuestReviewer` (token-based, no account) — reuses the entire
    existing invite flow, which is why this phase is cheap.
- Both paths email the applicant.
- Add a "Volunteer as a peer reviewer" link in the footer and on journal pages.

---

## Phase 6 — Publishing format + Paystack

The two heaviest items. Neither should start before Phases 1–5 are stable.

### 6.1 One house format for every article

The client's requirement — *"regardless of how the author sends their document,
the article needs to enter into that format"* — cannot be met by improving the
scraper. `extract_document_content()` guesses structure from bold runs and exact
keyword matches; it will keep mis-parsing real manuscripts. The reliable shape is
**extract → editor corrects → render from structured data**:

1. **Canonical schema.** Replace the loose `Article.extracted_sections` JSON with
   a defined structure, validated on save:
   ```json
   {
     "title": "", "subtitle": "",
     "authors": [{"name": "", "affiliation": "", "email": "", "orcid": ""}],
     "abstract": "", "keywords": [],
     "sections": [{"heading": "", "level": 1, "body_html": "",
                   "subsections": [...]}],
     "references": [{"raw": "", "doi": ""}],
     "funding": "", "acknowledgements": "", "conflict_of_interest": ""
   }
   ```
2. **Improve extraction** as a first pass only: use `docx` style names properly
   (Heading 1/2/3 nesting), keep italic/bold/superscript as inline HTML instead of
   flattening to text, and detect references by numbering/hanging-indent patterns
   rather than an exact-match heading list.
3. **Structured editor** — extend `preview_extracted_content` into a real
   correction screen: reorder sections, fix headings, split/merge, edit author
   block, paste references. **This is the step that guarantees the format**, and
   it's the one the current design lacks. Nothing publishes without passing
   through it.
4. **Single renderer.** One `article_render.html` partial driving both
   `article_detail.html` (web) and `article_pdf.html` (xhtml2pdf), so web and PDF
   cannot drift. House furniture: running head, journal name, volume/issue/pages,
   DOI, received/accepted/published dates, licence, and a copy-paste citation
   block (APA + a BibTeX download).
5. **`ArticleTemplate` per journal** (optional, low priority): section order,
   citation style, whether an abstract is mandatory.

> **Needed from the client before this starts:** a sample PDF or Word file of the
> exact house style they want — margins, type sizes, heading hierarchy, citation
> style (APA/MLA/Chicago), and the running-head/front-matter layout. Building this
> without the target spec means building it twice.

### 6.2 Paystack publication fee

```python
class JournalFee(models.Model):
    journal   = models.OneToOneField(Journal, related_name='fee')
    amount    = models.DecimalField(max_digits=10, decimal_places=2)   # NGN
    currency  = models.CharField(max_length=3, default='NGN')
    is_active = models.BooleanField(default=True)

class Payment(models.Model):
    STATUS = (('pending','Pending'), ('success','Success'),
              ('failed','Failed'), ('waived','Waived'))
    submission  = models.ForeignKey(Submission, related_name='payments')
    author      = models.ForeignKey(settings.AUTH_USER_MODEL, ...)
    amount, currency
    reference   = models.CharField(max_length=100, unique=True)  # our ref
    paystack_reference = models.CharField(max_length=100, blank=True)
    status      = models.CharField(choices=STATUS, default='pending')
    paid_at, raw_response (JSONField), waived_by, waiver_reason
```

Flow:

1. Chief editor approves → status `awaiting_payment`, `Payment` row created,
   author emailed with a pay link.
2. `payments/<submission_pk>/pay/` → Paystack **initialize transaction**
   (server-side, secret key never reaches the browser) → redirect to
   `authorization_url`.
3. `payments/callback/` verifies via **`GET /transaction/verify/:reference`** —
   the callback query string is not trusted on its own.
4. `payments/webhook/` — the authoritative path. Verify the
   `x-paystack-signature` HMAC-SHA512 against the raw request body, `csrf_exempt`,
   idempotent on reference. A user who closes the tab must still get credited.
5. On success → status `paid`; `publish_submission` unblocks.
6. **Waiver path** — a chief editor can mark a payment `waived` with a reason.
   Non-negotiable: student and invited submissions will need it.

Config (`.env` + `settings/base.py`, read via `python-decouple`):
`PAYSTACK_SECRET_KEY`, `PAYSTACK_PUBLIC_KEY`, `PAYSTACK_CALLBACK_URL`.
Use test keys (`sk_test_…`) throughout development. Add `requests` — already in
`requirements.txt`, so no new dependency.

Security notes: keys never in the repo; log every webhook to `logs/`; store the
full `raw_response` for reconciliation; put the webhook URL in the Paystack
dashboard and confirm the domain is HTTPS (AutoSSL is already active).

---

## Delivery order

| Phase | Item(s) | Rough size | Blocks |
|---|---|---|---|
| 1 | Per-journal roles | M | 2, 4, 5 |
| 2 | Rubrics UI, checklist, journal page | M | — |
| 3 | Remove statuses, author edit, wording | S | 4.2 (wording depends on 4.1) |
| 4 | Workflow rounds + blind-review enforcement | L | 6 |
| 5 | Volunteer reviewer portal | M | 1 |
| 6a | House publishing format | L | client spec |
| 6b | Paystack | M | 4 |

Phases 2 and 3 can run in parallel once 1 lands. Phase 5 is independent of 3/4.

**Migrations:** every change is additive (new models, new nullable fields, new
statuses). No destructive migration, no data loss. The one data migration is the
Phase 1 backfill granting existing staff `chief_editor` on all journals.

---

## Open questions for the client

1. **Statuses section** — remove the filter dropdown and stats tiles only, or the
   Status column as well? (Plan assumes dropdown + tiles; column stays.)
2. **Chief editor vs journal admin** — one person per journal doing both, or
   genuinely separate people? The plan supports separation; if it's always the
   same person, we can collapse to two roles.
3. **Publishing format** — need a sample of the target house style (see 6.1).
   Blocking for Phase 6a.
4. **Fee amounts** — same for every journal or per-journal? Who may waive?
   Charged per submission or per published article (i.e. refundable if rejected
   after payment)?
5. **Payment timing** — the brief says the author is notified for payment "once
   the article is ready for publishing". Confirming: payment gates *publication*,
   not submission, and a rejected article is never charged.
6. **Volunteer reviewers** — do approved volunteers get full logins, or stay
   token-based guests? (Plan supports both, admin chooses per applicant.)
