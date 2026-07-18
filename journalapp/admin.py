from django.contrib import admin
from .models import (
    CustomUser, Department, Profile, ArticleCategory, Article,
    Review, Comment, SiteSettings, HeroSlide, ArchivedJournal,
    Journal, Rubric, Submission, Assignment, SubmissionMessage,
    DocumentVersion, SubmissionLog
)


# Register User model
@admin.register(CustomUser)
class UserAdmin(admin.ModelAdmin):
    list_display = ('email', 'first_name', 'last_name', 'is_staff', 'is_active', 'date_joined')
    list_filter = ('is_staff', 'is_active')
    search_fields = ('email', 'first_name', 'last_name')
    ordering = ('-date_joined',)
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'first_name', 'last_name', 'password1', 'password2'),
        }),
    )

@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'code')
    search_fields = ('name', 'code')

@admin.register(Journal)
class JournalAdmin(admin.ModelAdmin):
    list_display = ('name', 'department')
    list_filter = ('department',)
    search_fields = ('name',)

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'department', 'is_editor', 'is_reviewer')
    list_filter = ('department', 'is_editor', 'is_reviewer')
    search_fields = ('user__email', 'user__first_name', 'user__last_name')

@admin.register(ArticleCategory)
class ArticleCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'journal')
    list_filter = ('journal',)
    search_fields = ('name',)

@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ('title', 'author', 'journal', 'status', 'created_at', 'published_at')
    list_filter = ('status', 'journal', 'category')
    search_fields = ('title', 'abstract', 'author__email', 'author__first_name', 'author__last_name')
    date_hierarchy = 'created_at'

@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('article', 'reviewer', 'decision', 'created_at')
    list_filter = ('decision',)
    search_fields = ('article__title', 'reviewer__email', 'reviewer__first_name', 'reviewer__last_name')

@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ('article', 'author', 'created_at')
    search_fields = ('article__title', 'author__email', 'author__first_name', 'author__last_name', 'content')

@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        # Prevent creating more than one instance
        return not SiteSettings.objects.exists()

@admin.register(HeroSlide)
class HeroSlideAdmin(admin.ModelAdmin):
    list_display = ('title', 'order', 'is_active')
    list_editable = ('order', 'is_active')
    list_filter = ('is_active',)

@admin.register(Rubric)
class RubricAdmin(admin.ModelAdmin):
    list_display = ('title', 'journal', 'order')
    list_filter = ('journal',)
    list_editable = ('order',)
    search_fields = ('title',)

@admin.register(ArchivedJournal)
class ArchivedJournalAdmin(admin.ModelAdmin):
    list_display = ('title', 'department', 'volume', 'issue', 'publication_date', 'featured', 'uploaded_by', 'uploaded_at')
    list_filter = ('department', 'publication_date', 'featured')
    list_editable = ('featured',)
    search_fields = ('title', 'description', 'volume', 'issue')
    date_hierarchy = 'publication_date'
    readonly_fields = ('uploaded_at', 'uploaded_by')
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('department', 'uploaded_by')
    
    def save_model(self, request, obj, form, change):
        if not change:  # Only set uploaded_by when creating a new object
            obj.uploaded_by = request.user
        super().save_model(request, obj, form, change)


# ============================================================================
# Submission Workflow Admin Models
# ============================================================================

class AssignmentInline(admin.TabularInline):
    model = Assignment
    extra = 0
    readonly_fields = ('assigned_at', 'completed_at')
    fields = ('assigned_to', 'assigned_by', 'role', 'status', 'assigned_at', 'completed_at')


class DocumentVersionInline(admin.TabularInline):
    model = DocumentVersion
    extra = 0
    readonly_fields = ('uploaded_at', 'version_number')
    fields = ('version_number', 'document', 'uploaded_by', 'notes', 'is_final', 'uploaded_at')


class SubmissionLogInline(admin.TabularInline):
    model = SubmissionLog
    extra = 0
    readonly_fields = ('timestamp', 'user', 'action', 'details')
    can_delete = False


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = ('title', 'author', 'journal', 'status', 'submitted_at', 'updated_at')
    list_filter = ('status', 'journal', 'submitted_at')
    search_fields = ('title', 'author__email', 'author__first_name', 'author__last_name')
    date_hierarchy = 'submitted_at'
    readonly_fields = ('submitted_at', 'updated_at')
    inlines = [AssignmentInline, DocumentVersionInline, SubmissionLogInline]

    fieldsets = (
        (None, {
            'fields': ('title', 'author', 'journal', 'document', 'status')
        }),
        ('Additional Info', {
            'fields': ('cover_letter', 'published_article'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('submitted_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = ('submission', 'assigned_to', 'role', 'status', 'assigned_at', 'completed_at')
    list_filter = ('role', 'status', 'assigned_at')
    search_fields = (
        'submission__title',
        'assigned_to__email', 'assigned_to__first_name', 'assigned_to__last_name',
        'assigned_by__email'
    )
    readonly_fields = ('assigned_at', 'completed_at')
    date_hierarchy = 'assigned_at'


@admin.register(SubmissionMessage)
class SubmissionMessageAdmin(admin.ModelAdmin):
    list_display = ('submission', 'sender', 'recipient', 'is_read', 'created_at')
    list_filter = ('is_read', 'created_at')
    search_fields = ('submission__title', 'sender__email', 'recipient__email', 'content')
    readonly_fields = ('created_at',)
    date_hierarchy = 'created_at'


@admin.register(DocumentVersion)
class DocumentVersionAdmin(admin.ModelAdmin):
    list_display = ('submission', 'version_number', 'uploaded_by', 'is_final', 'uploaded_at')
    list_filter = ('is_final', 'uploaded_at')
    search_fields = ('submission__title', 'uploaded_by__email', 'notes')
    readonly_fields = ('uploaded_at', 'version_number')
    date_hierarchy = 'uploaded_at'


@admin.register(SubmissionLog)
class SubmissionLogAdmin(admin.ModelAdmin):
    list_display = ('submission', 'user', 'action', 'timestamp')
    list_filter = ('timestamp',)
    search_fields = ('submission__title', 'user__email', 'action')
    readonly_fields = ('submission', 'user', 'action', 'details', 'timestamp')
    date_hierarchy = 'timestamp'

    def has_add_permission(self, request):
        return False  # Logs should only be created programmatically

    def has_change_permission(self, request, obj=None):
        return False  # Logs should not be edited
