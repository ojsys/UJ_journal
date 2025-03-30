from django.contrib import admin
from .models import CustomUser, Department, Profile, ArticleCategory, Article, Review, Comment, SiteSettings, HeroSlide


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

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'department', 'is_editor', 'is_reviewer')
    list_filter = ('department', 'is_editor', 'is_reviewer')
    search_fields = ('user__username', 'user__email')

@admin.register(ArticleCategory)
class ArticleCategoryAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)

@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ('title', 'author', 'department', 'status', 'created_at', 'published_at')
    list_filter = ('status', 'department', 'category')
    search_fields = ('title', 'abstract', 'author__username')
    date_hierarchy = 'created_at'

@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('article', 'reviewer', 'decision', 'created_at')
    list_filter = ('decision',)
    search_fields = ('article__title', 'reviewer__username')

@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ('article', 'author', 'created_at')
    search_fields = ('article__title', 'author__username', 'content')

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


# Add the ArchivedJournal to the imports
from .models import (
    Profile, Article, Review, Comment, Department, 
    SiteSettings, HeroSlide, ArticleCategory, ArchivedJournal
)

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