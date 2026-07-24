from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.urls import reverse
from django.utils import timezone
from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver
from ckeditor.fields import RichTextField
import uuid
from datetime import timedelta

################### Auth Models #########################
class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def get_by_natural_key(self, email):
        return self.get(email=email)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        
        return self.create_user(email, password, **extra_fields)

class CustomUser(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=30, blank=True)
    last_name = models.CharField(max_length=30, blank=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)
    
    objects = CustomUserManager()
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []
    
    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'
    
    def get_full_name(self):
        return f"{self.first_name} {self.last_name}".strip()
    
    def get_short_name(self):
        return self.first_name
    
    def __str__(self):
        return self.email

################### End Auth Models #########################


class Department(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=10, unique=True)
    description = models.TextField(blank=True)
    
    def __str__(self):
        return self.name


class Journal(models.Model):
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name='journals')
    name = models.CharField(max_length=200)
    description = RichTextField(blank=True)
    cover_image = models.ImageField(upload_to='journal_covers', blank=True, null=True)

    def __str__(self):
        return f"{self.name} ({self.department.name})"


class JournalRole(models.Model):
    """
    Grants a user a staff role scoped to a single journal.

    Before this model, every editorial view was gated on the site-wide
    ``is_staff`` flag, so any staff member could act on any journal. A role here
    is additive: site superusers and ``is_staff`` users keep full access (see
    ``journalapp.permissions``), while a journal role gives a non-staff user
    authority over exactly one journal.

    Two roles, because the client runs one lead person per journal:

    * ``chief_editor`` — full authority over the journal: content (rubrics,
      checklist, team) *and* the review workflow *and* final decisions
      (approve, reject, publish). This is the per-journal "admin".
    * ``editor`` — assists with the review workflow (assign reviewers, request
      revisions) but cannot take final decisions or manage journal content.
    """
    ROLE_CHIEF_EDITOR = 'chief_editor'
    ROLE_EDITOR = 'editor'

    ROLE_CHOICES = (
        (ROLE_CHIEF_EDITOR, 'Chief Editor'),    # full authority: content, workflow, publish
        (ROLE_EDITOR, 'Editor'),                # assists with review; no decisions, no content
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='journal_roles'
    )
    journal = models.ForeignKey(
        Journal,
        on_delete=models.CASCADE,
        related_name='roles'
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    granted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='journal_roles_granted'
    )
    granted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'journal', 'role')
        ordering = ['journal__name', 'role', 'user__email']
        verbose_name = 'Journal Role'
        verbose_name_plural = 'Journal Roles'

    def __str__(self):
        return f"{self.user.email} — {self.get_role_display()} of {self.journal.name}"


class SiteSettings(models.Model):
    site_title = models.CharField(max_length=100, default="University of Jos Journal System")
    site_description = models.TextField(blank=True)
    logo = models.ImageField(upload_to='site_images', blank=True, null=True)
    favicon = models.ImageField(upload_to='site_images', blank=True, null=True)
    primary_color = models.CharField(max_length=20, default="#007bff")
    secondary_color = models.CharField(max_length=20, default="#6c757d")
    footer_text = models.TextField(default="© University of Jos Journal System")
    contact_email = models.EmailField(default="contact@unijosjournals.edu.ng")
    contact_phone = models.CharField(max_length=20, blank=True)
    facebook_url = models.URLField(blank=True)
    twitter_url = models.URLField(blank=True)
    instagram_url = models.URLField(blank=True)
    linkedin_url = models.URLField(blank=True)
    
    class Meta:
        verbose_name = "Site Settings"
        verbose_name_plural = "Site Settings"
    
    def __str__(self):
        return "Site Settings"
    
    def save(self, *args, **kwargs):
        # Ensure only one instance exists
        if SiteSettings.objects.exists() and not self.pk:
            return
        return super().save(*args, **kwargs)

class HeroSlide(models.Model):
    title = models.CharField(max_length=200)
    subtitle = models.CharField(max_length=300, blank=True)
    image = models.ImageField(upload_to='hero_slides')
    button_text = models.CharField(max_length=50, blank=True)
    button_url = models.CharField(max_length=200, blank=True)
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['order']
    
    def __str__(self):
        return self.title


class Profile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True)
    bio = RichTextField(blank=True)
    profile_picture = models.ImageField(upload_to='profile_pics', blank=True, null=True)
    is_editor = models.BooleanField(default=False)
    is_reviewer = models.BooleanField(default=False)
    
    def __str__(self):
        return f"{self.user.email}'s Profile"

# Signal to create a profile when a user is created
@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)

# Signal to save the profile when the user is saved
@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def save_user_profile(sender, instance, **kwargs):
    try:
        instance.profile.save()
    except Profile.DoesNotExist:
        Profile.objects.create(user=instance)

class ArticleCategory(models.Model):
    journal = models.ForeignKey(Journal, on_delete=models.CASCADE, related_name='categories')
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    
    class Meta:
        verbose_name_plural = "Article Categories"
        unique_together = ('journal', 'name')

    def __str__(self):
        return f"{self.name} ({self.journal.name})"


class Rubric(models.Model):
    journal = models.ForeignKey(Journal, on_delete=models.CASCADE, related_name='rubrics')
    title = models.CharField(max_length=200)
    content = RichTextField()
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return self.title


class ChecklistItem(models.Model):
    """
    One thing an author must confirm before submitting to a journal.

    Each journal defines its own checklist (managed by its Chief Editor). At
    submission time the active items are rendered as checkboxes and the required
    ones must be ticked. What the author actually confirmed is frozen onto the
    :class:`ChecklistResponse` so later edits to the wording don't rewrite history.
    """
    journal = models.ForeignKey(
        Journal, on_delete=models.CASCADE, related_name='checklist_items'
    )
    text = models.CharField(max_length=500, help_text="The statement the author confirms.")
    help_text = models.CharField(
        max_length=500, blank=True,
        help_text="Optional clarifying note shown under the item."
    )
    order = models.PositiveIntegerField(default=0)
    required = models.BooleanField(
        default=True,
        help_text="If ticked, the author cannot submit without confirming this item."
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Inactive items are hidden from new submissions but kept for history."
    )

    class Meta:
        ordering = ['order', 'id']

    def __str__(self):
        return self.text[:80]


class ChecklistResponse(models.Model):
    """An author's answer to one checklist item, captured at submission time."""
    submission = models.ForeignKey(
        'Submission', on_delete=models.CASCADE, related_name='checklist_responses'
    )
    item = models.ForeignKey(
        ChecklistItem, on_delete=models.PROTECT, related_name='responses'
    )
    # Frozen copy: the item may be reworded or deactivated later, but this
    # records exactly what the author agreed to at the time.
    item_text = models.CharField(max_length=500)
    checked = models.BooleanField(default=False)
    responded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['item__order', 'item_id']
        unique_together = ('submission', 'item')

    def __str__(self):
        state = '✓' if self.checked else '✗'
        return f"{state} {self.item_text[:60]}"


class Article(models.Model):
    STATUS_CHOICES = (
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('under_review', 'Under Review'),
        ('revision_required', 'Revision Required'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
        ('published', 'Published'),
    )

    title = models.CharField(max_length=200)
    abstract = RichTextField()
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='articles')
    journal = models.ForeignKey(Journal, on_delete=models.CASCADE, related_name='articles', default=None, null=True)
    category = models.ForeignKey(ArticleCategory, on_delete=models.SET_NULL, null=True, blank=True)
    content = RichTextField()
    keywords = models.CharField(max_length=255, blank=True, help_text="Enter keywords separated by commas")
    file = models.FileField(upload_to='journal_files', blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    revised_document = models.FileField(upload_to='revised_documents/', null=True, blank=True)
    revision_notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    published_at = models.DateTimeField(null=True, blank=True)

    # Fields for extracted content from final Word document
    final_document = models.FileField(
        upload_to='final_documents/',
        blank=True,
        null=True,
        help_text="The final approved Word document"
    )
    extracted_citations = models.TextField(
        blank=True,
        help_text="References/citations extracted from the document"
    )
    extracted_sections = models.JSONField(
        default=list,
        blank=True,
        help_text="Structured sections extracted from the document"
    )

    # Publication metadata
    volume = models.CharField(max_length=50, blank=True)
    issue = models.CharField(max_length=50, blank=True)
    page_start = models.CharField(max_length=20, blank=True)
    page_end = models.CharField(max_length=20, blank=True)
    doi = models.CharField(max_length=100, blank=True, help_text="Digital Object Identifier")

    def publish(self):
        self.status = 'published'
        self.published_at = timezone.now()
        self.save()

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('article_detail', kwargs={'pk': self.pk})

    @property
    def page_numbers(self):
        """Return formatted page numbers"""
        if self.page_start and self.page_end:
            return f"{self.page_start}-{self.page_end}"
        return self.page_start or ""

    @property
    def keywords_list(self):
        """Return keywords as a list"""
        if self.keywords:
            return [k.strip() for k in self.keywords.split(',')]
        return []

class Review(models.Model):
    DECISION_CHOICES = (
        ('accept', 'Accept'),
        ('minor_revision', 'Minor Revision'),
        ('major_revision', 'Major Revision'),
        ('reject', 'Reject'),
    )
    
    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name='reviews')
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='reviews')
    comments = RichTextField()
    decision = models.CharField(max_length=20, choices=DECISION_CHOICES, default='minor_revision')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Review for {self.article.title} by {self.reviewer.email}"

class Comment(models.Model):
    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Comment by {self.author.email} on {self.article.title}"


class ArticleLog(models.Model):
    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name='logs')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=255)
    timestamp = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.article.title} - {self.action} at {self.timestamp}"



class ArchivedJournal(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name='archived_journals')
    volume = models.CharField(max_length=50, blank=True, null=True)
    issue = models.CharField(max_length=50, blank=True, null=True)
    publication_date = models.DateField()
    document = models.FileField(upload_to='archived_journals/')
    cover_image = models.ImageField(upload_to='archived_journal_covers/', blank=True, null=True)
    uploaded_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    featured = models.BooleanField(default=False, help_text="Feature this archive on the home page")

    class Meta:
        ordering = ['-publication_date']

    def __str__(self):
        return f"{self.title} - Vol. {self.volume}, Issue {self.issue}"


################### Submission Workflow Models #########################

class Submission(models.Model):
    """
    Represents an article submission in the review workflow.
    This is the central model for the new submission process.
    """
    STATUS_CHOICES = (
        ('pending', 'Pending Review'),
        ('preparing', 'Preparing for Review'),
        ('in_review', 'In Review'),
        ('with_editor', 'With Editor'),
        ('revision_requested', 'Revision Requested'),
        ('revised', 'Revised'),
        ('approved', 'Approved'),
        ('awaiting_payment', 'Awaiting Payment'),
        ('published', 'Published'),
        ('rejected', 'Rejected'),
    )

    # An author may correct/replace their own submission until an editor takes a
    # final decision — "so long as the admin has not accepted the submission"
    # (client). approved / published / rejected are final and lock it.
    AUTHOR_EDITABLE_STATES = (
        'pending', 'in_review', 'with_editor', 'revision_requested', 'revised',
    )

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='submissions'
    )
    journal = models.ForeignKey(
        Journal,
        on_delete=models.CASCADE,
        related_name='submissions'
    )
    title = models.CharField(max_length=300, blank=True, help_text="Title will be extracted from final document")
    document = models.FileField(
        upload_to='submissions/',
        help_text="Upload your article in Word document format (.docx)"
    )
    cover_letter = models.TextField(
        blank=True,
        help_text="Optional cover letter or notes for the editor"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    submitted_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # For blind peer review - anonymized identifier
    anonymized_identifier = models.CharField(
        max_length=50,
        unique=True,
        blank=True,
        help_text="Auto-generated anonymous identifier for blind review"
    )

    # For tracking the published article
    published_article = models.OneToOneField(
        Article,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='source_submission'
    )

    class Meta:
        ordering = ['-submitted_at']

    def __str__(self):
        return f"{self.title} by {self.author.get_full_name() or self.author.email}"

    def get_absolute_url(self):
        return reverse('submission_detail', kwargs={'pk': self.pk})

    def save(self, *args, **kwargs):
        """Generate anonymized identifier on first save"""
        if not self.anonymized_identifier:
            year = timezone.now().year
            # Get the count of submissions this year for incrementing
            count = Submission.objects.filter(
                submitted_at__year=year
            ).count() + 1
            self.anonymized_identifier = f"MS-{year}-{count:04d}"
        super().save(*args, **kwargs)

    @property
    def is_editable_by_author(self):
        """Whether the author may still edit/replace this submission."""
        return self.status in self.AUTHOR_EDITABLE_STATES

    # -- Blind review: hide the author from reviewers -----------------------

    def is_author_hidden_from(self, user):
        """Whether the author's identity must be hidden from ``user``.

        The author, site staff, and this journal's editorial team always see the
        real identity. A reviewer sees it only if their assignment is *not*
        blinded. Anyone else (including anonymous) is hidden by default, so a
        template that forgets to guard a name can't leak it.
        """
        if not (user and getattr(user, 'is_authenticated', False)):
            return True
        if user == self.author or user.is_staff or user.is_superuser:
            return False
        if self.journal.roles.filter(user=user).exists():
            return False
        assignment = self.assignments.filter(assigned_to=user).first()
        if assignment:
            return bool(assignment.blinded)
        return True

    def author_label_for(self, user):
        """The author's name for ``user``, or the manuscript code if hidden."""
        if self.is_author_hidden_from(user):
            return self.anonymized_identifier
        return self.author.get_full_name() or self.author.email

    # -- Review rounds ------------------------------------------------------

    @property
    def current_round(self):
        """The latest review round, if any."""
        return self.review_rounds.order_by('-number').first()

    def open_new_round(self, opened_by=None):
        """Open the next review round (closing any still-open one)."""
        last = self.current_round
        if last and last.closed_at is None:
            last.closed_at = timezone.now()
            last.save(update_fields=['closed_at'])
        number = (last.number + 1) if last else 1
        return self.review_rounds.create(number=number, opened_by=opened_by)

    @property
    def has_review_copy(self):
        """Whether a reviewer-ready (de-identified) copy exists."""
        return self.document_versions.filter(is_review_copy=True).exists()

    # -- Publication fee ----------------------------------------------------

    @property
    def active_fee(self):
        """The journal's active publication fee, or None if there's no charge."""
        fee = getattr(self.journal, 'fee', None)
        if fee and fee.is_active and fee.amount and fee.amount > 0:
            return fee
        return None

    @property
    def is_paid(self):
        """Whether the publication fee is settled (paid or waived)."""
        return self.payments.filter(status__in=('success', 'waived')).exists()

    @property
    def requires_payment(self):
        """Whether publication is currently blocked pending a fee."""
        return self.active_fee is not None and not self.is_paid

    @property
    def current_assignments(self):
        """Get all active assignments for this submission"""
        return self.assignments.filter(status='active')

    @property
    def reviewers(self):
        """Get all assigned reviewers"""
        return self.assignments.filter(role='reviewer', status='active')

    @property
    def editors(self):
        """Get all assigned editors"""
        return self.assignments.filter(role='editor', status='active')


class GuestReviewer(models.Model):
    """
    Represents external reviewers who don't have accounts on the platform.
    Admin can add them and send review invitations via email.
    """
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    affiliation = models.CharField(
        max_length=300,
        blank=True,
        help_text="Institution or organization affiliation"
    )
    expertise_areas = models.TextField(
        blank=True,
        help_text="Areas of expertise (comma-separated)"
    )
    invitation_token = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        help_text="Unique token for accessing the platform"
    )
    token_expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Token expiration date"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this guest reviewer can receive new assignments"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_guest_reviewers'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_full_name()} ({self.email})"

    def get_full_name(self):
        """Return full name of the guest reviewer"""
        return f"{self.first_name} {self.last_name}".strip()

    def save(self, *args, **kwargs):
        """Set token expiration on creation"""
        if not self.pk and not self.token_expires_at:
            # Token expires in 90 days by default
            self.token_expires_at = timezone.now() + timedelta(days=90)
        super().save(*args, **kwargs)

    def regenerate_token(self):
        """Generate a new invitation token"""
        self.invitation_token = uuid.uuid4()
        self.token_expires_at = timezone.now() + timedelta(days=90)
        self.save()

    def is_token_valid(self):
        """Check if the invitation token is still valid"""
        if not self.is_active:
            return False
        if self.token_expires_at and timezone.now() > self.token_expires_at:
            return False
        return True


class ReviewRound(models.Model):
    """
    One round of peer review on a submission.

    A submission may go through several rounds: reviewers report, the author
    revises, the editor sends it back out. Grouping assignments under a round
    makes the second round distinguishable from the first in the history.
    """
    submission = models.ForeignKey(
        Submission, on_delete=models.CASCADE, related_name='review_rounds'
    )
    number = models.PositiveIntegerField()
    opened_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    opened_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='review_rounds_opened'
    )

    class Meta:
        ordering = ['submission', 'number']
        unique_together = ('submission', 'number')

    def __str__(self):
        return f"{self.submission.anonymized_identifier} — round {self.number}"


class Assignment(models.Model):
    """
    Tracks reviewer and editor assignments to submissions.
    Supports both regular users and guest reviewers.
    """
    ROLE_CHOICES = (
        ('reviewer', 'Reviewer'),
        ('editor', 'Editor'),
    )

    STATUS_CHOICES = (
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('declined', 'Declined'),
    )

    submission = models.ForeignKey(
        Submission,
        on_delete=models.CASCADE,
        related_name='assignments'
    )
    # Either assigned_to OR guest_reviewer must be set (not both)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='assigned_submissions',
        null=True,
        blank=True,
        help_text="Regular user assigned to review"
    )
    guest_reviewer = models.ForeignKey(
        'GuestReviewer',
        on_delete=models.CASCADE,
        related_name='assignments',
        null=True,
        blank=True,
        help_text="Guest reviewer assigned to review"
    )
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='assignments_made'
    )
    review_round = models.ForeignKey(
        ReviewRound,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assignments',
        help_text="Which review round this assignment belongs to"
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    assigned_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True, help_text="Notes about this assignment")

    # For guest reviewer access
    access_token = models.CharField(
        max_length=100,
        unique=True,
        blank=True,
        null=True,
        help_text="Unique access token for guest reviewers"
    )

    # For blind peer review
    blinded = models.BooleanField(
        default=True,
        help_text="Whether author information should be hidden from reviewer"
    )

    # Reviewer's feedback
    feedback = models.TextField(blank=True, help_text="Feedback from reviewer/editor")
    recommendation = models.CharField(
        max_length=50,
        blank=True,
        choices=(
            ('approve', 'Approve for Publication'),
            ('minor_revision', 'Minor Revisions Needed'),
            ('major_revision', 'Major Revisions Needed'),
            ('reject', 'Reject'),
        )
    )
    amended_document = models.FileField(
        upload_to='amended_documents/',
        blank=True,
        null=True,
        help_text="Amended document with reviewer's annotations and corrections"
    )

    class Meta:
        ordering = ['-assigned_at']

    def __str__(self):
        reviewer_name = self.reviewer_name
        return f"{self.get_role_display()}: {reviewer_name} for {self.submission.title}"

    def save(self, *args, **kwargs):
        """Generate access token for guest reviewers"""
        if self.guest_reviewer and not self.access_token:
            # Generate a unique access token for guest reviewers
            self.access_token = str(uuid.uuid4())
        super().save(*args, **kwargs)

    def clean(self):
        """Validate that either assigned_to or guest_reviewer is set, but not both"""
        from django.core.exceptions import ValidationError
        if not self.assigned_to and not self.guest_reviewer:
            raise ValidationError("Either assigned_to or guest_reviewer must be set.")
        if self.assigned_to and self.guest_reviewer:
            raise ValidationError("Cannot assign both a user and a guest reviewer.")

    @property
    def reviewer_name(self):
        """Return the name of the reviewer (user or guest)"""
        if self.assigned_to:
            return self.assigned_to.get_full_name() or self.assigned_to.email
        elif self.guest_reviewer:
            return self.guest_reviewer.get_full_name()
        return "Unknown Reviewer"

    @property
    def reviewer_email(self):
        """Return the email of the reviewer (user or guest)"""
        if self.assigned_to:
            return self.assigned_to.email
        elif self.guest_reviewer:
            return self.guest_reviewer.email
        return None

    @property
    def is_guest_assignment(self):
        """Check if this is a guest reviewer assignment"""
        return self.guest_reviewer is not None

    def complete(self, feedback='', recommendation=''):
        """Mark assignment as completed"""
        self.status = 'completed'
        self.completed_at = timezone.now()
        if feedback:
            self.feedback = feedback
        if recommendation:
            self.recommendation = recommendation
        self.save()


class SubmissionMessage(models.Model):
    """
    Chat messages between admin, reviewers, and editors about a submission.
    """
    submission = models.ForeignKey(
        Submission,
        on_delete=models.CASCADE,
        related_name='messages'
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sent_messages'
    )
    # If recipient is null, it's a group message visible to all participants
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='received_messages',
        null=True,
        blank=True,
        help_text="Leave empty for group message"
    )
    content = models.TextField()
    attachment = models.FileField(
        upload_to='chat_attachments/',
        blank=True,
        null=True,
        help_text="Optional file attachment"
    )
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        recipient_str = self.recipient.email if self.recipient else "All"
        return f"Message from {self.sender.email} to {recipient_str}"


class DocumentVersion(models.Model):
    """
    Tracks different versions of documents uploaded during the review process.
    """
    submission = models.ForeignKey(
        Submission,
        on_delete=models.CASCADE,
        related_name='document_versions'
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='uploaded_documents'
    )
    document = models.FileField(upload_to='submissions/versions/')
    version_number = models.PositiveIntegerField()
    notes = models.TextField(blank=True, help_text="Notes about this version")
    uploaded_at = models.DateTimeField(auto_now_add=True)
    is_final = models.BooleanField(
        default=False,
        help_text="Mark as the final approved version"
    )
    is_review_copy = models.BooleanField(
        default=False,
        help_text="A Chief-Editor-prepared, de-identified copy that reviewers "
                  "download. Reviewers only ever see review copies, never the "
                  "author's original upload."
    )

    class Meta:
        ordering = ['-version_number']
        unique_together = ['submission', 'version_number']

    def __str__(self):
        return f"{self.submission.title} - Version {self.version_number}"

    def save(self, *args, **kwargs):
        if not self.version_number:
            # Auto-increment version number
            last_version = DocumentVersion.objects.filter(
                submission=self.submission
            ).order_by('-version_number').first()
            self.version_number = (last_version.version_number + 1) if last_version else 1
        super().save(*args, **kwargs)


class SubmissionLog(models.Model):
    """
    Activity log for tracking all actions on a submission.
    """
    submission = models.ForeignKey(
        Submission,
        on_delete=models.CASCADE,
        related_name='logs'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    action = models.CharField(max_length=255)
    details = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional details about this action"
    )
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.submission.title} - {self.action} at {self.timestamp}"


################### End Submission Workflow Models #########################


################### Volunteer Reviewer Applications #########################

class ReviewerApplication(models.Model):
    """
    A public application to become a volunteer peer reviewer.

    Anyone may apply without an account. An editor reviews the application and,
    on approval, turns the applicant into either a full login account (a
    ``CustomUser`` with ``Profile.is_reviewer``) or a token-based
    :class:`GuestReviewer` — reusing the existing guest-invite machinery.
    """
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    )

    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField()
    affiliation = models.CharField(
        max_length=300, blank=True,
        help_text="Institution or organization"
    )
    position = models.CharField(
        max_length=200, blank=True,
        help_text="Role or title, e.g. Senior Lecturer"
    )
    qualifications = models.TextField(
        blank=True,
        help_text="Degrees, publications, relevant experience"
    )
    expertise_areas = models.TextField(
        blank=True,
        help_text="Areas of expertise (comma-separated)"
    )
    journals_of_interest = models.ManyToManyField(
        Journal, blank=True, related_name='reviewer_applications'
    )
    cv = models.FileField(upload_to='reviewer_cvs/', blank=True, null=True)
    statement = models.TextField(
        blank=True,
        help_text="A short statement of interest"
    )

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='reviewer_applications_reviewed'
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_notes = models.TextField(blank=True)

    # Set when an approved applicant is turned into an account or guest reviewer.
    created_user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='reviewer_application'
    )
    guest_reviewer = models.OneToOneField(
        GuestReviewer, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='reviewer_application'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_full_name()} ({self.email}) — {self.get_status_display()}"

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def expertise_list(self):
        return [a.strip() for a in self.expertise_areas.split(',') if a.strip()]


################### End Volunteer Reviewer Applications #########################


################### Publication Fees & Payments #########################

class JournalFee(models.Model):
    """The publication fee charged for a journal, payable before an accepted
    article is published. A journal without an active fee publishes for free."""
    journal = models.OneToOneField(Journal, on_delete=models.CASCADE, related_name='fee')
    amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text="Amount charged on acceptance, before publication."
    )
    currency = models.CharField(max_length=3, default='NGN')
    is_active = models.BooleanField(
        default=True,
        help_text="Uncheck to publish this journal free of charge."
    )
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.journal.name}: {self.currency} {self.amount}"


class Payment(models.Model):
    """A publication-fee payment attempt for a submission (via Paystack)."""
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('waived', 'Waived'),
    )

    submission = models.ForeignKey(
        Submission, on_delete=models.CASCADE, related_name='payments'
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='payments'
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='NGN')

    # Our own reference, sent to Paystack; unique so webhooks are idempotent.
    reference = models.CharField(max_length=100, unique=True)
    paystack_reference = models.CharField(max_length=100, blank=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    paid_at = models.DateTimeField(null=True, blank=True)
    raw_response = models.JSONField(default=dict, blank=True)

    waived_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='payments_waived'
    )
    waiver_reason = models.CharField(max_length=300, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.reference} — {self.get_status_display()} ({self.currency} {self.amount})"

    @property
    def amount_kobo(self):
        """Paystack works in the currency's minor unit (kobo for NGN)."""
        return int(self.amount * 100)


################### End Publication Fees & Payments #########################
