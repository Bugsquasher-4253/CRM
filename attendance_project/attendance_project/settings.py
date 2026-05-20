import os
import dj_database_url
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# ── SECURITY ──────────────────────────────────────────────────────────────────
SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-6z^hccjv#h0^uxvw9grxs+c04_bbg=m52g7dk!&tt=p^3!5f#1')

DEBUG = os.environ.get('DEBUG', 'False') == 'True'

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
        conn_max_age=0,
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
# Store sessions in DB so all server instances share the same sessions
SESSION_ENGINE   = 'django.contrib.sessions.backends.db'
SESSION_COOKIE_AGE      = 43200   # 12 hours
SESSION_COOKIE_HTTPONLY = True
SESSION_SAVE_EVERY_REQUEST = False

# ── SECURITY HEADERS ──────────────────────────────────────────────────────────
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS             = 'DENY'
CSRF_COOKIE_HTTPONLY        = True

# On Vercel (HTTPS), enforce secure cookies and trust the proxy header
if not DEBUG:
    SESSION_COOKIE_SECURE       = True
    CSRF_COOKIE_SECURE          = True
    SECURE_PROXY_SSL_HEADER     = ('HTTP_X_FORWARDED_PROTO', 'https')
