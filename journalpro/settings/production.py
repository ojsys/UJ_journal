"""
Production settings for University of Jos Journal System.

These settings are for production deployment.
Make sure to set all required environment variables!
"""

import os

from .base import *
from decouple import config, Csv

# Ensure the log directory exists so file logging never fails on a fresh deploy.
LOGS_DIR = BASE_DIR / 'logs'
os.makedirs(LOGS_DIR, exist_ok=True)

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = config('SECRET_KEY')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = False

# Hosts/domain names that are valid for this site
ALLOWED_HOSTS = config('ALLOWED_HOSTS', cast=Csv())



DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': config('DB_NAME'),
        'USER': config('DB_USER'),
        'PASSWORD': config('DB_PASSWORD'),
        'HOST': config('DB_HOST', default='localhost'),
        'PORT': config('DB_PORT', default='3306'),
        'CONN_MAX_AGE': 60,
        'OPTIONS': {'charset': 'utf8mb4'},
    }
}

# Database
# PostgreSQL for production
# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.postgresql',
#         'NAME': config('DB_NAME'),
#         'USER': config('DB_USER'),
#         'PASSWORD': config('DB_PASSWORD'),
#         'HOST': config('DB_HOST', default='localhost'),
#         'PORT': config('DB_PORT', default='5432'),
#         'CONN_MAX_AGE': 60,
#         'OPTIONS': {
#             'connect_timeout': 10,
#         },
#     }
# }


# Static files
STATIC_ROOT = BASE_DIR / 'staticfiles'

# WhiteNoise for serving static files in production
MIDDLEWARE.insert(1, 'whitenoise.middleware.WhiteNoiseMiddleware')
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'


# Security settings
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

# HTTPS settings
SECURE_SSL_REDIRECT = config('SECURE_SSL_REDIRECT', default=True, cast=bool)
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# Proxy settings (for reverse proxy like nginx)
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
USE_X_FORWARDED_HOST = True


# Email settings for production
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = config('EMAIL_HOST', default='smtp.gmail.com')
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
EMAIL_HOST_USER = config('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD')
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='noreply@unijosjournals.edu.ng')
SERVER_EMAIL = config('SERVER_EMAIL', default='server@unijosjournals.edu.ng')


# Logging for production
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {name} {module}:{lineno:d} pid:{process:d} {message}',
            'style': '{',
        },
    },
    'filters': {
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse',
        },
    },
    'handlers': {
        # Rotating error log: 5 MB per file, keep 5 backups (~30 MB cap total).
        'error_file': {
            'level': 'ERROR',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': LOGS_DIR / 'django_error.log',
            'maxBytes': 5 * 1024 * 1024,
            'backupCount': 5,
            'encoding': 'utf-8',
            'formatter': 'verbose',
        },
        # Separate rotating log for warnings (kept out of the error file for clarity).
        'warning_file': {
            'level': 'WARNING',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': LOGS_DIR / 'django_warning.log',
            'maxBytes': 2 * 1024 * 1024,
            'backupCount': 3,
            'encoding': 'utf-8',
            'formatter': 'verbose',
        },
        # Emails admins on 500s — only when DEBUG is off and email/ADMINS are set.
        'mail_admins': {
            'level': 'ERROR',
            'class': 'django.utils.log.AdminEmailHandler',
            'filters': ['require_debug_false'],
            'include_html': True,
        },
    },
    # Catch-all: any ERROR (incl. third-party libs) lands in the error file.
    'root': {
        'handlers': ['error_file'],
        'level': 'ERROR',
    },
    'loggers': {
        'django': {
            'handlers': ['error_file', 'warning_file'],
            'level': 'WARNING',
            'propagate': False,
        },
        # Unhandled 500s are logged here with a full traceback.
        'django.request': {
            'handlers': ['error_file', 'mail_admins'],
            'level': 'ERROR',
            'propagate': False,
        },
        # This project's own log calls: logging.getLogger('journalapp').
        'journalapp': {
            'handlers': ['error_file', 'warning_file', 'mail_admins'],
            'level': 'WARNING',
            'propagate': False,
        },
    },
}


# Cache settings for production.
# Database-backed cache — no Redis/Memcached needed (works on shared cPanel).
# Create the table once with: python manage.py createcachetable
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.db.DatabaseCache',
        'LOCATION': 'django_cache_table',
    }
}


# Session settings for production.
# Store sessions in the database, not the cache (avoids any Redis dependency).
SESSION_ENGINE = 'django.contrib.sessions.backends.db'


# File upload settings
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10 MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10 MB


# Admin settings
ADMINS = [
    ('Admin', config('ADMIN_EMAIL', default='admin@unijosjournals.edu.ng')),
]
MANAGERS = ADMINS


# Media files storage (optional: use cloud storage like S3)
# AWS_ACCESS_KEY_ID = config('AWS_ACCESS_KEY_ID', default='')
# AWS_SECRET_ACCESS_KEY = config('AWS_SECRET_ACCESS_KEY', default='')
# AWS_STORAGE_BUCKET_NAME = config('AWS_STORAGE_BUCKET_NAME', default='')
# AWS_S3_REGION_NAME = config('AWS_S3_REGION_NAME', default='us-east-1')
# AWS_S3_FILE_OVERWRITE = False
# AWS_DEFAULT_ACL = None
# DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'


# Performance optimizations
CONN_MAX_AGE = 60  # Database connection persistence
