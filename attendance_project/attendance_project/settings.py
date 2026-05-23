import os
import dj_database_url
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# ── SECURITY ──────────────────────────────────────────────────────────────────
SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-6z^hccjv#h0^uxvw9grxs+c04_bbg=m52g7dk!&tt=p^3!5f#1')

DEBUG = os.environ.get('DEBUG', 'False') == 'True'

# Base URL used to build absolute links in emails (no trailing slash)
SITE_URL = os.environ.get('SITE_URL', 'http://127.0.0.1:8000')

ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', 'localhost 127.0.0.1').split() + ['.vercel.app']

# Required for HTTPS form/login POSTs on a custom domain (Django 4+).
CSRF_TRUSTED_ORIGINS = os.environ.get('CSRF_TRUSTED_ORIGINS', 'https://*.vercel.app').split()

# ── APPS ──────────────────────────────────────────────────────────────────────
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "attendance",
]

# ── MIDDLEWARE ────────────────────────────────────────────────────────────────
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",   # serve static files
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "attendance_project.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "attendance.context_processors.panel_context",
            ],
        },
    },
]

WSGI_APPLICATION = "attendance_project.wsgi.application"

# ── DATABASE ──────────────────────────────────────────────────────────────────
DATABASES = {
    "default": dj_database_url.config(
        default=f'sqlite:///{BASE_DIR / "db.sqlite3"}',
        # 60 s lets warm Vercel instances reuse the connection while avoiding
        # the stale-connection error Neon throws after it scales to zero.
        conn_max_age=60,
        ssl_require=False,
    )
}
# SQLite: increase lock timeout so concurrent writes queue instead of crashing
if DATABASES['default']['ENGINE'] == 'django.db.backends.sqlite3':
    DATABASES['default'].setdefault('OPTIONS', {})['timeout'] = 30

# ── PASSWORD VALIDATION ───────────────────────────────────────────────────────
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ── INTERNATIONALISATION ──────────────────────────────────────────────────────
LANGUAGE_CODE = "en-us"
TIME_ZONE     = "Asia/Kolkata"
USE_I18N      = True
USE_TZ        = True

# ── STATIC FILES ──────────────────────────────────────────────────────────────
STATIC_URL  = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
    },
}

# ── MEDIA FILES ───────────────────────────────────────────────────────────────
MEDIA_URL  = "/media/"
# In production, set MEDIA_ROOT to a persistent path (e.g. /var/www/hrms/media on EC2).
# Falls back to /tmp/media (Vercel's only writable dir) when the env var is unset.
MEDIA_ROOT = Path(os.environ.get('MEDIA_ROOT', '/tmp/media')) if not DEBUG else BASE_DIR / "media"

# ── AUTH ──────────────────────────────────────────────────────────────────────
LOGIN_URL            = "/"
LOGIN_REDIRECT_URL   = "/dashboard/"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ── SESSIONS ──────────────────────────────────────────────────────────────────
# Signed cookies: session data lives in the browser cookie (signed, not encrypted,
# but httponly so JS can't read it). Eliminates one DB round-trip per request
# compared to the db backend — significant on Neon serverless.
SESSION_ENGINE          = 'django.contrib.sessions.backends.signed_cookies'
SESSION_COOKIE_AGE      = 43200   # 12 hours
SESSION_COOKIE_HTTPONLY = True
SESSION_SAVE_EVERY_REQUEST = False

# ── EMAIL ────────────────────────────────────────────────────────────────────
EMAIL_HOST          = os.environ.get('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT          = int(os.environ.get('EMAIL_PORT', '587'))
EMAIL_USE_TLS       = os.environ.get('EMAIL_USE_TLS', 'True') == 'True'
EMAIL_HOST_USER     = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL  = os.environ.get('DEFAULT_FROM_EMAIL', EMAIL_HOST_USER) or 'noreply@crefio.in'
ADMIN_NOTIFICATION_EMAIL = os.environ.get('ADMIN_EMAIL', EMAIL_HOST_USER)

# Fall back to console when no SMTP credentials are configured (local dev)
if EMAIL_HOST_USER:
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
else:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# ── SECURITY HEADERS ──────────────────────────────────────────────────────────
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS             = 'DENY'
CSRF_COOKIE_HTTPONLY        = True

# On Vercel (HTTPS), enforce secure cookies and trust the proxy header
if not DEBUG:
    SESSION_COOKIE_SECURE       = True
    CSRF_COOKIE_SECURE          = True
    SECURE_PROXY_SSL_HEADER     = ('HTTP_X_FORWARDED_PROTO', 'https')
