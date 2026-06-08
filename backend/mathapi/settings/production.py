from .base import *
import dj_database_url

DEBUG = False

ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='*').split(',')

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

# CORS — allow the frontend Render URL
CORS_ALLOWED_ORIGINS = [
    o for o in config('CORS_ALLOWED_ORIGINS', default='').split(',') if o.strip()
]
CORS_ALLOW_ALL_ORIGINS = config('CORS_ALLOW_ALL_ORIGINS', default=False, cast=bool)

# Disable Celery if no Redis is configured
CELERY_TASK_ALWAYS_EAGER = True
