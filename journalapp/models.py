from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.urls import reverse
from django.utils import timezone
from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver
from ckeditor.fields import RichTextField

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
    journal_title = models.CharField(max_length=200, blank=True)
    journal_description = RichTextField(blank=True)
    cover_image = models.ImageField(upload_to='department_covers', blank=True, null=True)
    
    def __str__(self):
        return self.name
    
    def get_journal_title(self):
        return self.journal_title if self.journal_title else f"{self.name} Journal"


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
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    is_default = models.BooleanField(default=False)
    
    class Meta:
        verbose_name_plural = "Categories"
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        # If this is marked as default, unmark all others
        if self.is_default:
            ArticleCategory.objects.filter(is_default=True).update(is_default=False)
        # If no default exists, mark this as default
        elif not ArticleCategory.objects.filter(is_default=True).exists():
            self.is_default = True
        super().save(*args, **kwargs)

    @classmethod
    def get_default(cls):
        default = cls.objects.filter(is_default=True).first()
        if not default:
            default = cls.objects.first()
            if default:
                default.is_default = True
                default.save()
        return default

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
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='journals')
    department = models.ForeignKey(Department, on_delete=models.CASCADE)
    category = models.ForeignKey(ArticleCategory, on_delete=models.CASCADE)
    content = RichTextField()
    keywords = models.CharField(max_length=255, blank=True, help_text="Enter keywords separated by commas")
    file = models.FileField(upload_to='journal_files', blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    published_at = models.DateTimeField(null=True, blank=True)
    
    def publish(self):
        self.status = 'published'
        self.published_at = timezone.now()
        self.save()
    
    def __str__(self):
        return self.title
    
    def get_absolute_url(self):
        return reverse('article_detail', kwargs={'pk': self.pk})

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
    decision = models.CharField(max_length=20, choices=DECISION_CHOICES, default='miror_revision')
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