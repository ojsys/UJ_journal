from django.contrib import admin
from .models import (
    CustomUser, Department, Profile, ArticleCategory, Article,
    Review, Comment, SiteSettings, HeroSlide,
    Journal, Issue, EditorialBoardMember, JournalPage,
    Rubric, Submission, Assignment, SubmissionMessage,
    DocumentVersion, SubmissionLog, JournalRole, ChecklistItem, ChecklistResponse,
    ReviewRound, ReviewerApplication, JournalFee, Payment
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

class JournalRoleInline(admin.TabularInline):
    model = JournalRole
    extra = 0
    fk_name = 'journal'
    autocomplete_fields = ('user',)
    readonly_fields = ('granted_at',)
    fields = ('user', 'role', 'granted_by', 'granted_at')


class EditorialBoardMemberInline(admin.TabularInline):
    model = EditorialBoardMember
    extra = 0
    fields = ('name', 'position', 'section', 'affiliation', 'order', 'is_active')


class JournalPageInline(admin.TabularInline):
    model = JournalPage
    extra = 0
    prepopulated_fields = {'slug': ('title',)}
    fields = ('title', 'slug', 'order', 'show_in_nav', 'is_published')


@admin.register(Journal)
class JournalAdmin(admin.ModelAdmin):
    list_display = ('name', 'abbreviation', 'slug', 'order', 'is_active',
                    'issue_count', 'team_size')
    list_filter = ('is_active', 'department')
    list_editable = ('order', 'is_active')
    search_fields = ('name', 'abbreviation', 'slug')
    prepopulated_fields = {'slug': ('name',)}
    inlines = [EditorialBoardMemberInline, JournalPageInline, JournalRoleInline]
    fieldsets = (
        ('Identity', {
            'fields': ('name', 'slug', 'abbreviation', 'tagline', 'logo', 'cover_image')
        }),
        ('About', {'fields': ('description', 'about')}),
        ('Publication details', {
            'fields': ('issn_print', 'issn_online', 'published_by', 'contact_email')
        }),
        ('Placement', {'fields': ('department', 'order', 'is_active')}),
    )

    @admin.display(description='Editorial team')
    def team_size(self, obj):
        return obj.roles.count()

    @admin.display(description='Issues')
    def issue_count(self, obj):
        return obj.issues.count()


@admin.register(Issue)
class IssueAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'journal', 'year', 'published_date',
                    'article_count', 'is_published', 'featured')
    list_filter = ('journal', 'year', 'is_published', 'featured')
    search_fields = ('title', 'volume', 'number', 'journal__name')
    date_hierarchy = 'published_date'

    @admin.display(description='Articles')
    def article_count(self, obj):
        return obj.articles.count()


@admin.register(EditorialBoardMember)
class EditorialBoardMemberAdmin(admin.ModelAdmin):
    list_display = ('name', 'position', 'journal', 'section', 'affiliation',
                    'order', 'is_active')
    list_filter = ('journal', 'section', 'is_active')
    search_fields = ('name', 'position', 'affiliation')
    autocomplete_fields = ('user',)


@admin.register(JournalPage)
class JournalPageAdmin(admin.ModelAdmin):
    list_display = ('title', 'journal', 'slug', 'order', 'show_in_nav', 'is_published')
    list_filter = ('journal', 'is_published', 'show_in_nav')
    search_fields = ('title', 'content')
    prepopulated_fields = {'slug': ('title',)}


@admin.register(JournalRole)
class JournalRoleAdmin(admin.ModelAdmin):
    list_display = ('user', 'journal', 'role', 'granted_by', 'granted_at')
    list_filter = ('role', 'journal')
    search_fields = ('user__email', 'user__first_name', 'user__last_name', 'journal__name')
    autocomplete_fields = ('user', 'journal')
    readonly_fields = ('granted_at',)

    def save_model(self, request, obj, form, change):
        if not change and not obj.granted_by:
            obj.granted_by = request.user
        super().save_model(request, obj, form, change)

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


@admin.register(ChecklistItem)
class ChecklistItemAdmin(admin.ModelAdmin):
    list_display = ('text', 'journal', 'required', 'is_active', 'order')
    list_filter = ('journal', 'required', 'is_active')
    list_editable = ('required', 'is_active', 'order')
    search_fields = ('text',)


@admin.register(ChecklistResponse)
class ChecklistResponseAdmin(admin.ModelAdmin):
    list_display = ('submission', 'item_text', 'checked', 'responded_at')
    list_filter = ('checked', 'responded_at')
    search_fields = ('submission__title', 'item_text')
    readonly_fields = ('submission', 'item', 'item_text', 'checked', 'responded_at')

    def has_add_permission(self, request):
        return False

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
    list_display = ('submission', 'version_number', 'uploaded_by', 'is_final', 'is_review_copy', 'uploaded_at')
    list_filter = ('is_final', 'is_review_copy', 'uploaded_at')
    search_fields = ('submission__title', 'uploaded_by__email', 'notes')
    readonly_fields = ('uploaded_at', 'version_number')
    date_hierarchy = 'uploaded_at'


@admin.register(ReviewRound)
class ReviewRoundAdmin(admin.ModelAdmin):
    list_display = ('submission', 'number', 'opened_at', 'closed_at', 'opened_by')
    list_filter = ('opened_at',)
    search_fields = ('submission__title',)
    readonly_fields = ('opened_at',)


@admin.register(JournalFee)
class JournalFeeAdmin(admin.ModelAdmin):
    list_display = ('journal', 'amount', 'currency', 'is_active', 'updated_at')
    list_filter = ('is_active', 'currency')
    search_fields = ('journal__name',)


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('reference', 'submission', 'author', 'amount', 'currency', 'status', 'paid_at')
    list_filter = ('status', 'currency', 'created_at')
    search_fields = ('reference', 'paystack_reference', 'author__email', 'submission__title')
    readonly_fields = ('reference', 'paystack_reference', 'raw_response', 'paid_at',
                       'created_at', 'updated_at')
    date_hierarchy = 'created_at'


@admin.register(ReviewerApplication)
class ReviewerApplicationAdmin(admin.ModelAdmin):
    list_display = ('get_full_name', 'email', 'affiliation', 'status', 'created_at', 'reviewed_by')
    list_filter = ('status', 'created_at')
    search_fields = ('first_name', 'last_name', 'email', 'affiliation', 'expertise_areas')
    filter_horizontal = ('journals_of_interest',)
    readonly_fields = ('created_at', 'updated_at', 'reviewed_at', 'created_user', 'guest_reviewer')
    date_hierarchy = 'created_at'


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
