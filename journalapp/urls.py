from django.urls import path
from django.contrib.auth import views as auth_views
from . import views
from . import submission_views

urlpatterns = [
    path('', views.home, name='home'),
    path('register/', views.register, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('profile/', views.profile, name='profile'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('dashboard/author/', views.author_dashboard, name='author_dashboard'),
    path('dashboard/editor/', views.editor_dashboard, name='editor_dashboard'),
    path('dashboard/reviewer/', views.reviewer_dashboard, name='reviewer_dashboard'),
    path('dashboard/admin/', views.admin_dashboard, name='admin_dashboard'),
    
    # Department Journal URLs
    path('departments/<int:department_id>/journal/', views.department_journal, name='department_journal'),
    path('journals/', views.JournalListView.as_view(), name='journal_list'),
    
    # Article URLs (renamed from Journal)
    path('articles/', views.ArticleListView.as_view(), name='article_list'),
    path('articles/<int:pk>/', views.ArticleDetailView.as_view(), name='article_detail'),
    path('articles/new/<int:journal_id>/', views.ArticleCreateView.as_view(), name='article_create'),
    path('articles/<int:pk>/update/', views.ArticleUpdateView.as_view(), name='article_update'),
    path('articles/<int:pk>/delete/', views.ArticleDeleteView.as_view(), name='article_delete'),
    path('api/parse-document/', views.parse_document, name='parse_document'),
    path('articles/<int:pk>/submit/', views.submit_article, name='submit_article'),
    path('article/<int:article_id>/assign-reviewer/', views.assign_reviewer, name='assign_reviewer'),
    path('articles/<int:pk>/review/', views.review_article, name='review_article'),
    path('articles/<int:pk>/publish/', views.publish_article, name='publish_article'),
    #Download PDF view
    path('articles/<int:pk>/pdf/', views.article_pdf, name='article_pdf'),
    path('article/<int:pk>/upload-revised/', views.upload_revised_document, name='upload_revised_document'),
    path('articles/search/', views.ArticleSearchView.as_view(), name='article_search'),

    path('management/site-settings/', views.site_settings, name='site_settings'),
    path('management/hero-slides/', views.hero_slides, name='hero_slides'),
    path('management/hero-slides/create/', views.hero_slide_create, name='hero_slide_create'),
    path('management/hero-slides/<int:pk>/update/', views.hero_slide_update, name='hero_slide_update'),
    path('management/hero-slides/<int:pk>/delete/', views.hero_slide_delete, name='hero_slide_delete'),
    # Add these URL patterns
    path('admin/archived-journals/', views.archived_journals_list, name='archived_journals_list'),
    path('admin/archived-journals/create/', views.archived_journal_create, name='archived_journal_create'),
    path('admin/archived-journals/<int:pk>/update/', views.archived_journal_update, name='archived_journal_update'),
    path('admin/archived-journals/<int:pk>/delete/', views.archived_journal_delete, name='archived_journal_delete'),
    path('archives/', views.public_archived_journals, name='public_archived_journals'),
    path('archives/<int:pk>/', views.archived_journal_detail, name='archived_journal_detail'),
    
    # Password reset URLs
    path('password-reset/',
         auth_views.PasswordResetView.as_view(template_name='journalapp/password_reset.html'),
         name='password_reset'),
    path('password-reset/done/',
         auth_views.PasswordResetDoneView.as_view(template_name='journalapp/password_reset_done.html'),
         name='password_reset_done'),
    path('password-reset-confirm/<uidb64>/<token>/',
         auth_views.PasswordResetConfirmView.as_view(template_name='journalapp/password_reset_confirm.html'),
         name='password_reset_confirm'),
    path('password-reset-complete/',
         auth_views.PasswordResetCompleteView.as_view(template_name='journalapp/password_reset_complete.html'),
         name='password_reset_complete'),

    # ============================================================================
    # Submission Workflow URLs
    # ============================================================================

    # Author submission URLs
    path('submissions/', submission_views.submission_list, name='submission_list'),
    path('submissions/new/', submission_views.submission_create, name='submission_create'),
    path('submissions/<int:pk>/', submission_views.submission_detail, name='submission_detail'),
    path('submissions/<int:pk>/revise/', submission_views.submission_revise, name='submission_revise'),

    # Admin submission management URLs
    path('manage/submissions/', submission_views.admin_submission_list, name='admin_submission_list'),
    path('manage/submissions/<int:pk>/', submission_views.admin_submission_detail, name='admin_submission_detail'),
    path('manage/submissions/<int:pk>/assign/', submission_views.assign_submission, name='assign_submission'),
    path('manage/submissions/<int:pk>/request-revision/', submission_views.request_revision, name='request_revision'),
    path('manage/submissions/<int:pk>/upload-final/', submission_views.upload_final_document, name='upload_final_document'),
    path('manage/submissions/<int:pk>/preview/', submission_views.preview_extracted_content, name='preview_extracted_content'),
    path('manage/submissions/<int:pk>/publish/', submission_views.publish_submission, name='publish_submission'),
    path('manage/submissions/<int:pk>/reject/', submission_views.reject_submission, name='reject_submission'),
    path('manage/submissions/<int:pk>/approve/', submission_views.approve_submission, name='approve_submission'),
    path('manage/submissions/<int:pk>/share-with-author/', submission_views.share_with_author, name='share_with_author'),

    # Reviewer/Editor URLs
    path('my-assignments/', submission_views.my_assignments, name='my_assignments'),
    path('assignments/<int:pk>/work/', submission_views.work_on_submission, name='work_on_submission'),

    # Chat/Messaging API URLs
    path('api/submissions/<int:submission_id>/messages/', submission_views.get_messages, name='get_messages'),
    path('api/submissions/<int:submission_id>/messages/send/', submission_views.send_message, name='send_message'),
    path('api/messages/unread-count/', submission_views.unread_message_count, name='unread_message_count'),

    # Document download
    path('documents/<int:version_id>/download/', submission_views.download_document, name='download_document'),

    # ============================================================================
    # Guest Reviewer Management URLs (Staff Only)
    # ============================================================================
    path('manage/guest-reviewers/', submission_views.manage_guest_reviewers, name='manage_guest_reviewers'),
    path('manage/guest-reviewers/add/', submission_views.add_guest_reviewer, name='add_guest_reviewer'),
    path('manage/guest-reviewers/bulk-add/', submission_views.bulk_add_guest_reviewers, name='bulk_add_guest_reviewers'),
    path('manage/guest-reviewers/<int:pk>/edit/', submission_views.edit_guest_reviewer, name='edit_guest_reviewer'),
    path('manage/guest-reviewers/<int:pk>/resend/', submission_views.resend_guest_invitation, name='resend_guest_invitation'),

    # ============================================================================
    # Guest Review Access URLs (No Login Required)
    # ============================================================================
    path('guest-review/<uuid:token>/', submission_views.guest_review_access, name='guest_review_access'),
    path('guest-review/<int:submission_id>/<str:access_token>/', submission_views.guest_work_on_submission, name='guest_work_on_submission'),
    path('guest-review/<int:submission_id>/<str:access_token>/submitted/', submission_views.guest_feedback_submitted, name='guest_feedback_submitted'),
    path('guest-review/download/<int:version_id>/<str:access_token>/', submission_views.guest_download_document, name='guest_download_document'),
]