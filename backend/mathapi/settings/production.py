from .base import *
import dj_database_url
from django.core.exceptions import ImproperlyConfigured

DEBUG = False

_allowed_hosts = config('ALLOWED_HOSTS', default='')
if not _allowed_hosts.strip():
    raise ImproperlyConfigured(
        'ALLOWED_HOSTS is not set for the production settings module. '
        'A wildcard default here would accept any Host header, enabling '
        'cache-poisoning and password-reset-link-poisoning attacks. Set '
        'ALLOWED_HOSTS to your real domain(s), comma-separated.'
    )
ALLOWED_HOSTS = [h.strip() for h in _allowed_hosts.split(',') if h.strip()]

# PostgreSQL from Render
DATABASES = {
    'default': dj_database_url.config(
        env='DATABASE_URL',
        conn_max_age=600,
        conn_health_checks=True,
    )
}

# WhiteNoise for static files
MIDDLEWARE.insert(1, 'whitenoise.middleware.WhiteNoiseMiddleware')
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Security
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = False  # Render handles TLS termination
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
X_FRAME_OPTIONS = 'DENY'
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = 'same-origin'
# HSTS — only takes effect once the site is confirmed to be served over
# HTTPS end-to-end (Render's TLS termination + SECURE_PROXY_SSL_HEADER
# above). Starts at 1 day so a misconfiguration doesn't lock browsers out
# of the site for a year; raise once HTTPS is verified stable.
SECURE_HSTS_SECONDS = config('SECURE_HSTS_SECONDS', default=86400, cast=int)
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = False

# CORS — allow the frontend Render URL
CORS_ALLOWED_ORIGINS = [
    o for o in config('CORS_ALLOWED_ORIGINS', default='').split(',') if o.strip()
]
CORS_ALLOW_ALL_ORIGINS = config('CORS_ALLOW_ALL_ORIGINS', default=False, cast=bool)

# Disable Celery if no Redis is configured
CELERY_TASK_ALWAYS_EAGER = True
