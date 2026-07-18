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
        ('in_review', 'In Review'),
        ('with_editor', 'With Editor'),
        ('revision_requested', 'Revision Requested'),
        ('revised', 'Revised'),
        ('approved', 'Approved'),
        ('published', 'Published'),
        ('rejected', 'Rejected'),
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
