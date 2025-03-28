from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('register/', views.register, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('profile/', views.profile, name='profile'),
    path('dashboard/', views.dashboard, name='dashboard'),
    
    # Department Journal URLs
    path('departments/<int:department_id>/journal/', views.department_journal, name='department_journal'),
    path('journals/', views.JournalListView.as_view(), name='journal_list'),
    
    # Article URLs (renamed from Journal)
    path('articles/', views.ArticleListView.as_view(), name='article_list'),
    path('articles/<int:pk>/', views.ArticleDetailView.as_view(), name='article_detail'),
    path('articles/new/', views.ArticleCreateView.as_view(), name='article_create'),
    path('articles/<int:pk>/update/', views.ArticleUpdateView.as_view(), name='article_update'),
    path('articles/<int:pk>/delete/', views.ArticleDeleteView.as_view(), name='article_delete'),
    path('articles/<int:pk>/submit/', views.submit_article, name='submit_article'),
    path('articles/<int:pk>/review/', views.review_article, name='review_article'),
    path('articles/<int:pk>/publish/', views.publish_article, name='publish_article'),
    #Download PDF view
    path('articles/<int:pk>/pdf/', views.article_pdf, name='article_pdf'),
    
    path('management/site-settings/', views.site_settings, name='site_settings'),
    path('management/hero-slides/', views.hero_slides, name='hero_slides'),
    path('management/hero-slides/create/', views.hero_slide_create, name='hero_slide_create'),
    path('management/hero-slides/<int:pk>/update/', views.hero_slide_update, name='hero_slide_update'),
    path('management/hero-slides/<int:pk>/delete/', views.hero_slide_delete, name='hero_slide_delete'),


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
]