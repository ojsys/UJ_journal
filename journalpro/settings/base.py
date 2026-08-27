"""
Base settings for University of Jos Journal System.

These settings are common to both development and production environments.
"""

from pathlib import Path
from decouple import config, Csv
import os

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent.parent


# Application definition

INSTALLED_APPS = [
    'jazzmin',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'journalapp',
    'crispy_forms',
    'crispy_bootstrap5',
    'django_filters',
    'ckeditor',
    'django.contrib.humanize',
]


# CKEditor Configuration
CKEDITOR_CONFIGS = {
    'default': {
        'toolbar': 'full',
        'height': 300,
        'width': '100%',
    },
}

# Jazzmin Settings
JAZZMIN_SETTINGS = {
    "site_title": "UJ Journal Admin",
    "site_header": "UJ Journal",
    "site_brand": "UJ Journal",
    "site_logo_classes": "img-circle",
    "login_logo_classes": "img-circle",
    "welcome_sign": "Welcome to University of Jos Journal System",
    "copyright": "University of Jos Journal System",
    "search_model": "journalapp.Article",
    "user_avatar": None,
    "topmenu_links": [
        {"name": "Home", "url": "admin:index", "permissions": ["auth.view_user"]},
        {"name": "Support", "url": "https://github.com/farridav/django-jazzmin/issues", "new_window": True},
        {"model": "auth.User"},
        {"app": "journalapp"},
    ],
    "usermenu_links": [
        {"name": "Support", "url": "https://github.com/farridav/django-jazzmin/issues", "new_window": True},
        {"model": "auth.user"}
    ],
    "show_sidebar": True,
    "navigation_expanded": True,
    "hide_apps": [],
    "hide_models": [],
    "order_with_respect_to": ["auth", "journalapp"],
    "icons": {
        "auth": "fas fa-users-cog",
        "auth.user": "fas fa-user",
        "auth.Group": "fas fa-users",
        "journalapp.article": "fas fa-newspaper",
        "journalapp.department": "fas fa-building",
        "journalapp.profile": "fas fa-id-card",
        "journalapp.review": "fas fa-check-double",
        "journalapp.comment": "fas fa-comments",
        "journalapp.sitesettings": "fas fa-cogs",
        "journalapp.heroslide": "fas fa-images",
        "journalapp.submission": "fas fa-file-upload",
        "journalapp.assignment": "fas fa-user-check",
        "journalapp.submissionmessage": "fas fa-envelope",
        "journalapp.documentversion": "fas fa-file-alt",
        "journalapp.submissionlog": "fas fa-history",
    },
    "default_icon_parents": "fas fa-folder",
    "default_icon_children": "fas fa-file",
    "related_modal_active": True,
    "custom_css": None,
    "custom_js": None,
    "show_ui_builder": True,
    "changeform_format": "horizontal_tabs",
    "changeform_format_overrides": {
        "auth.user": "collapsible",
        "auth.group": "vertical_tabs",
    },
}

# Crispy Forms Configuration
CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"


MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'journalpro.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'journalapp.context_processors.site_settings',
                'journalapp.context_processors.journal_roles',
                'journalapp.context_processors.nav_journals',
            ],
        },
    },
]

WSGI_APPLICATION = 'journalpro.wsgi.application'


# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True


# Static files (CSS, JavaScript, Images)
STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'


# Custom User Model
AUTH_USER_MODEL = 'journalapp.CustomUser'

# Login/Logout redirects
LOGIN_REDIRECT_URL = '/dashboard/'
LOGOUT_REDIRECT_URL = '/'
LOGIN_URL = '/login/'

AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
]

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# ---------------------------------------------------------------------------
# Paystack (publication fees) — read from .env; blank disables payments.
# Use test keys (sk_test_… / pk_test_…) in development.
# ---------------------------------------------------------------------------
PAYSTACK_SECRET_KEY = config('PAYSTACK_SECRET_KEY', default='')
PAYSTACK_PUBLIC_KEY = config('PAYSTACK_PUBLIC_KEY', default='')
# Where Paystack sends the browser back after payment. Leave blank to use the
# in-app callback route built from the current request host.
PAYSTACK_CALLBACK_URL = config('PAYSTACK_CALLBACK_URL', default='')
