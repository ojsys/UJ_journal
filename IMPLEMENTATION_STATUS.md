# Anonymous Peer Review & Guest Reviewer System - Implementation Status

**Date:** November 27, 2025
**Status:** Phase 1 Complete | Phase 2 In Progress

---

## ✅ COMPLETED FEATURES

### 1. Author Anonymization (Blind Peer Review)

#### Database & Models ✅
- **Submission Model** (`journalapp/models.py:320`)
  - Added `anonymized_identifier` field (auto-generates "MS-YEAR-####")
  - Custom `save()` method generates unique IDs
  - Migration successful with data population for existing records

- **Assignment Model** (`journalapp/models.py:485`)
  - Added `blinded` field (BooleanField, default=True)
  - Updated to support both regular users and guest reviewers
  - Added helper properties: `reviewer_name`, `reviewer_email`, `is_guest_assignment`

#### Templates Updated ✅
- **work_on_submission.html** - Shows Manuscript ID instead of author name when blinded
- **reviewer_dashboard.html** - Hides author names in assignment cards
- **editor_dashboard.html** - Hides author names in assignment cards
- **Message System** - Shows anonymized ID for author messages to reviewers

#### Document Sanitization ✅
- **Created:** `journalapp/utils.py`
  - `sanitize_document_metadata()` - Removes author info from Word docs
  - `get_sanitized_filename()` - Generates sanitized filenames
- **Updated:** `download_document` view (`submission_views.py:929`)
  - Serves sanitized documents to blinded reviewers
  - Preserves original for authors and admins

### 2. Guest Reviewer Models & Forms

#### Models ✅
- **GuestReviewer Model** (`journalapp/models.py:412`)
  - Fields: email, first_name, last_name, affiliation, expertise_areas
  - UUID-based invitation tokens
  - Token expiration (90 days default)
  - Methods: `get_full_name()`, `regenerate_token()`, `is_token_valid()`

- **Assignment Model Extensions** (`journalapp/models.py:485`)
  - `guest_reviewer` ForeignKey (nullable)
  - `access_token` for guest access (auto-generated UUID)
  - `assigned_to` now nullable (either user OR guest)
  - Validation: Ensures only one reviewer type per assignment

#### Forms ✅
- **GuestReviewerForm** (`journalapp/forms.py:441`)
  - Add/edit single guest reviewer
  - Email uniqueness validation

- **BulkGuestReviewerForm** (`journalapp/forms.py:489`)
  - CSV/line-separated bulk import
  - Format: email, first_name, last_name, affiliation
  - Validates all entries before import

- **AssignGuestReviewerForm** (`journalapp/forms.py:555`)
  - Unified form for assigning any reviewer type
  - Radio selection: existing_guest, new_guest, registered_user
  - Conditional validation based on selection

#### Email Templates ✅
Created in `journalapp/templates/emails/`:
1. **guest_reviewer_invitation.html** - Initial invitation to join platform
2. **guest_assignment_notification.html** - Assignment to specific submission
3. **guest_feedback_confirmation.html** - Review submission confirmation
4. **admin_guest_feedback_notification.html** - Notifies admin of new feedback

### 3. Database Migrations ✅
- **Migration 0006** successfully applied
- Data migration populated existing submissions with anonymized IDs
- Verified in database:
  - Submission 1: MS-2025-0001
  - Submission 2: MS-2025-0002
  - All assignments have blinded=True

---

## 🔄 REMAINING WORK

### Critical Components Needed:

### 1. Guest Reviewer Management Views
**File:** `journalapp/submission_views.py` (add new views)

#### Views to Create:

```python
@staff_member_required
def add_guest_reviewer(request):
    """Add a single guest reviewer and send invitation"""
    # Use GuestReviewerForm
    # On success: create GuestReviewer, send invitation email
    # Redirect to manage_guest_reviewers

@staff_member_required
def bulk_add_guest_reviewers(request):
    """Add multiple guest reviewers from CSV"""
    # Use BulkGuestReviewerForm
    # Parse CSV, create GuestReviewers in bulk
    # Send batch invitation emails
    # Show summary of created/failed

@staff_member_required
def manage_guest_reviewers(request):
    """List and manage all guest reviewers"""
    # List all GuestReviewers
    # Filter: active/inactive, search by email/name
    # Actions: edit, deactivate, regenerate token, resend invite

@staff_member_required
def edit_guest_reviewer(request, pk):
    """Edit guest reviewer details"""
    # Use GuestReviewerForm
    # Update existing GuestReviewer

@staff_member_required
def resend_guest_invitation(request, pk):
    """Regenerate token and resend invitation"""
    # Call regenerate_token()
    # Send email with new token
```

### 2. Guest Review Access Views (No Login Required)

```python
def guest_review_access(request, token):
    """Landing page for guest reviewers using invitation token"""
    # Validate invitation_token
    # Show list of assignments for this guest
    # Provide links to each assignment

def guest_work_on_submission(request, submission_id, access_token):
    """Guest reviewer interface (similar to work_on_submission)"""
    # Validate access_token from Assignment
    # Show submission details (anonymized if blinded)
    # Show document versions (sanitized if blinded)
    # Display feedback form
    # NO chat functionality (simplified)

def submit_guest_feedback(request, submission_id, access_token):
    """Handle guest feedback submission"""
    # Validate access_token
    # Update Assignment: feedback, recommendation, amended_document
    # Mark assignment as completed
    # Send confirmation email to guest
    # Send notification email to admin
    # Redirect to thank you page
```

### 3. Update Existing Views

#### assign_submission view
**Location:** `journalapp/submission_views.py`

**Changes needed:**
```python
# Replace SubmissionAssignmentForm with AssignGuestReviewerForm
# Handle three types of assignments:
# 1. registered_user: Create Assignment with assigned_to
# 2. existing_guest: Create Assignment with guest_reviewer
# 3. new_guest: Create GuestReviewer first, then Assignment

# Send appropriate email:
# - Regular user: existing notification
# - Guest reviewer: guest_assignment_notification.html
```

### 4. Templates to Create

#### Guest Reviewer Management Templates
**Location:** `journalapp/templates/submissions/`

1. **admin_add_guest_reviewer.html**
   - Form to add single guest
   - GuestReviewerForm display
   - Option to assign immediately after creation

2. **admin_bulk_add_guests.html**
   - Textarea for CSV input
   - Format instructions
   - Preview table before confirming
   - Batch invitation button

3. **admin_manage_guests.html**
   - Table of all guest reviewers
   - Columns: name, email, affiliation, active, created, actions
   - Search/filter functionality
   - Actions: edit, deactivate, resend invitation

#### Guest Review Interface Templates
**Location:** `journalapp/templates/submissions/`

1. **guest_review_access.html**
   - Landing page after clicking invitation link
   - Welcome message with guest name
   - List of active assignments
   - Links to review each assignment

2. **guest_work_on_submission.html**
   - Simplified version of work_on_submission.html
   - Remove chat section
   - Show manuscript ID (if blinded) or author info
   - Document version list with download
   - Feedback form (recommendation + text + upload)

3. **guest_feedback_submitted.html**
   - Thank you page
   - Confirmation message
   - Reference number
   - Contact information

#### Update Admin Templates

**admin_submission_detail.html**
```html
<!-- In assignments section, update to show: -->
{% for assignment in submission.assignments.all %}
  <div class="assignment-card">
    <strong>{{ assignment.get_role_display }}:</strong>
    {% if assignment.is_guest_assignment %}
      <span class="badge badge-info">Guest</span>
      {{ assignment.guest_reviewer.get_full_name }}
      ({{ assignment.guest_reviewer.email }})
    {% else %}
      {{ assignment.assigned_to.get_full_name }}
    {% endif %}
    <span class="badge">{{ assignment.get_status_display }}</span>
  </div>
{% endfor %}
```

### 5. URL Patterns to Add
**File:** `journalapp/urls.py`

```python
# Guest reviewer management (staff only)
path('admin/guest-reviewers/add/', views.add_guest_reviewer, name='add_guest_reviewer'),
path('admin/guest-reviewers/bulk-add/', views.bulk_add_guest_reviewers, name='bulk_add_guest_reviewers'),
path('admin/guest-reviewers/', views.manage_guest_reviewers, name='manage_guest_reviewers'),
path('admin/guest-reviewers/<int:pk>/edit/', views.edit_guest_reviewer, name='edit_guest_reviewer'),
path('admin/guest-reviewers/<int:pk>/resend/', views.resend_guest_invitation, name='resend_guest_invitation'),

# Guest review access (no login required)
path('submissions/guest-review/<uuid:token>/', views.guest_review_access, name='guest_review_access'),
path('submissions/<int:submission_id>/guest-review/<str:access_token>/', views.guest_work_on_submission, name='guest_work_on_submission'),
path('submissions/<int:submission_id>/guest-review/<str:access_token>/submit/', views.submit_guest_feedback, name='submit_guest_feedback'),
```

### 6. Email Sending Functions

**Create helper function in submission_views.py:**

```python
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
        from_email=f'{site_name} <{settings.DEFAULT_FROM_EMAIL}>',
        to=[guest_reviewer.email]
    )
    email.attach_alternative(html_content, "text/html")
    email.send()

def send_guest_assignment_email(assignment, request):
    """Send assignment notification to guest reviewer"""
    # Similar structure, use guest_assignment_notification.html
    pass

def send_guest_feedback_confirmation(assignment, request):
    """Send confirmation to guest after submission"""
    # Use guest_feedback_confirmation.html
    pass

def send_admin_feedback_notification(assignment, request):
    """Notify admin of new guest feedback"""
    # Use admin_guest_feedback_notification.html
    # Send to all staff users
    pass
```

---

## 📋 TESTING CHECKLIST

### Author Anonymization Tests
- [ ] Log in as reviewer
- [ ] Check dashboard - should show manuscript IDs not author names
- [ ] Open assignment - should display "MS-2025-XXXX" not author
- [ ] Download document - filename should be "MS-2025-XXXX.docx"
- [ ] Check messages - author messages should show manuscript ID
- [ ] Log in as admin - should still see author names
- [ ] Log in as author - should see own name

### Guest Reviewer System Tests
- [ ] Admin: Add single guest reviewer
- [ ] Admin: Bulk add guest reviewers via CSV
- [ ] Admin: View all guest reviewers
- [ ] Guest: Receive invitation email
- [ ] Guest: Click invitation link
- [ ] Guest: See list of assignments
- [ ] Admin: Assign guest to submission
- [ ] Guest: Receive assignment email
- [ ] Guest: Click review link
- [ ] Guest: Download document (sanitized if blinded)
- [ ] Guest: Submit feedback
- [ ] Guest: Receive confirmation email
- [ ] Admin: Receive notification email
- [ ] Admin: View guest feedback in admin panel

---

## 🎯 IMPLEMENTATION PRIORITY

### High Priority (Core Functionality)
1. Guest review access views (token-based)
2. Update assign_submission view
3. Guest review interface template
4. URL patterns

### Medium Priority (Admin Tools)
1. Add single guest reviewer view
2. Manage guest reviewers view
3. Management templates

### Low Priority (Nice to Have)
1. Bulk add functionality
2. Advanced filtering
3. Guest reviewer analytics

---

## 📝 NOTES

### Security Considerations
- ✅ UUID tokens for guest access
- ✅ Token expiration implemented
- ⚠️ Add rate limiting for guest endpoints
- ⚠️ Log all guest access attempts
- ⚠️ Validate tokens on every request

### Dependencies
- ✅ python-docx installed (for document sanitization)
- ✅ Django email backend configured
- ⚠️ Ensure SMTP settings in production

### Future Enhancements
- Guest reviewer expertise matching
- Automatic reviewer suggestions based on keywords
- Review quality ratings
- Reviewer conflict of interest tracking
- Deadline reminders
- Multi-language support for emails

---

## 🔗 KEY FILE LOCATIONS

### Models
- `journalapp/models.py` (lines 320-621)

### Forms
- `journalapp/forms.py` (lines 441-690)

### Views
- `journalapp/submission_views.py` (needs new views)

### Templates
- `journalapp/templates/submissions/` (existing)
- `journalapp/templates/emails/` (4 new templates created)

### Migrations
- `journalapp/migrations/0006_*.py` (applied successfully)

### Utilities
- `journalapp/utils.py` (document sanitization)

---

**Last Updated:** November 27, 2025
**Next Steps:** Implement guest review access views and update assign_submission view
