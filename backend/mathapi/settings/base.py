from pathlib import Path
from decouple import config
from datetime import timedelta
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent.parent

_INSECURE_DEFAULT_KEY = 'django-insecure-change-me-in-production-mathplatform-key'
SECRET_KEY = config('SECRET_KEY', default=_INSECURE_DEFAULT_KEY)

# DEBUG defaults to False — safe-by-default. Local development must
# explicitly opt in via `.env` (DEBUG=True). This matters because a
# forgotten/missing .env on a real deployment used to silently run with
# DEBUG=True, which leaks stack traces, local variables, and file paths to
# anyone who can trigger a server error.
DEBUG = config('DEBUG', default=False, cast=bool)

# A DEBUG=False process is never allowed to run with the publicly-known
# placeholder SECRET_KEY — that key is committed to git history (visible in
# every clone of this repo) and its exact value ships in this settings
# file, so anyone who has ever seen this codebase can forge session/JWT
# tokens for ANY user, including super_admin, if this check didn't exist.
if not DEBUG and SECRET_KEY == _INSECURE_DEFAULT_KEY:
    raise ImproperlyConfigured(
        'SECRET_KEY is not set. Generate a real one (e.g. `python -c '
        '"import secrets; print(secrets.token_urlsafe(50))"`) and set it as '
        'SECRET_KEY in your .env before running with DEBUG=False.'
    )

ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1').split(',')

DJANGO_APPS = [
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

THIRD_PARTY_APPS = [
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
    'django_filters',
]

LOCAL_APPS = [
    'mathapi.apps.accounts',
    'mathapi.apps.students',
    'mathapi.apps.exams',
    'mathapi.apps.analytics',
    'mathapi.apps.reports',
    'mathapi.apps.groups',
    'mathapi.apps.notifications',
    'mathapi.apps.gamification',
    'mathapi.apps.quizzes',
    'mathapi.apps.tournaments',
    'mathapi.apps.leagues',
    'mathapi.apps.interventions',
]

# admin MUST come after local apps so Django sees the custom
# User model (accounts.User) before running admin migrations.
INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS + ['django.contrib.admin']

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'mathapi.apps.accounts.middleware.AuditMiddleware',
]

ROOT_URLCONF = 'mathapi.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'mathapi.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

AUTH_USER_MODEL = 'accounts.User'

# JWT Settings
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=8),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True,
    'ALGORITHM': 'HS256',
    'AUTH_HEADER_TYPES': ('Bearer',),
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
}

# DRF Settings
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
        'rest_framework.throttling.ScopedRateThrottle',
    ],
    # 'anon'/'user' are broad safety nets so no endpoint is ever fully
    # unthrottled. 'login' is deliberately much stricter and applied only
    # to the login view — the highest-value target for credential
    # brute-forcing — without slowing down normal authenticated use.
    'DEFAULT_THROTTLE_RATES': {
        'anon': '60/min',
        'user': '300/min',
        'login': '10/min',
    },
}

# Without page_size_query_param set, DRF silently ignores any ?page_size=
# query param and every list endpoint is hard-capped at PAGE_SIZE (20) per
# page. The frontend relies on being able to request larger pages in several
# places — offline sync (usePWASync), report/bulk-import dropdowns, and the
# "load everything for client-side filtering" hooks — so without this, those
# features were silently truncating data to the first 20 rows.
REST_FRAMEWORK['DEFAULT_PAGINATION_CLASS'] = 'mathapi.core.pagination.LargePageNumberPagination'

# CORS
CORS_ALLOWED_ORIGINS = config(
    'CORS_ALLOWED_ORIGINS',
    default='http://localhost:5173,http://127.0.0.1:5173'
).split(',')
CORS_ALLOW_CREDENTIALS = True

# Celery
CELERY_BROKER_URL = config('REDIS_URL', default='redis://localhost:6379/0')
CELERY_RESULT_BACKEND = config('REDIS_URL', default='redis://localhost:6379/0')

# Email
# Free by design: no paid transactional-email service required. Point
# EMAIL_HOST at any SMTP relay with a free tier — Gmail SMTP (smtp.gmail.com,
# port 587, an App Password — not your normal password — as EMAIL_HOST_PASSWORD),
# Brevo/Sendinblue (free ~300/day), Zoho Mail, or your school's own mail
# server all work with zero code changes, just env vars. Leave EMAIL_HOST
# unset (the default) and emails print to the console instead — handy for
# local dev without touching real inboxes.
EMAIL_HOST = config('EMAIL_HOST', default='')
if EMAIL_HOST:
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
    EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
    EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
    EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
    EMAIL_USE_SSL = config('EMAIL_USE_SSL', default=False, cast=bool)
    EMAIL_TIMEOUT = config('EMAIL_TIMEOUT', default=15, cast=int)
else:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='noreply@mathplatform.edu')

# WhatsApp (via Twilio's WhatsApp Business API)
# Same "free by design until you opt in" pattern as email: leave
# TWILIO_ACCOUNT_SID unset and messages just get logged instead of sent —
# handy for local dev, and means WhatsApp support never requires a paid
# account to run the platform. Twilio's WhatsApp Sandbox is free for
# development; a production sender number requires WhatsApp Business
# approval through Twilio (or another routing later, if ever needed) but
# no code changes.
TWILIO_ACCOUNT_SID = config('TWILIO_ACCOUNT_SID', default='')
TWILIO_AUTH_TOKEN = config('TWILIO_AUTH_TOKEN', default='')
TWILIO_WHATSAPP_FROM = config('TWILIO_WHATSAPP_FROM', default='whatsapp:+14155238886')  # Twilio sandbox default

# Base URL of the deployed frontend, used to build links inside notification
# emails (e.g. "View student" → FRONTEND_URL + /analytics/student/<id>).
FRONTEND_URL = config('FRONTEND_URL', default='http://localhost:5173').rstrip('/')

# Shared secret an external free scheduler (GitHub Actions cron, cron-job.org)
# must send as the X-Cron-Secret header to trigger /api/notifications/cron/*.
# Blank means those endpoints refuse to run — set this before relying on them.
CRON_SECRET = config('CRON_SECRET', default='')

