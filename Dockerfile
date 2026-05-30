FROM python:3.12.3-slim

# System dependencies needed by psycopg2 and health check
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first (layer cache — only reinstalls if requirements.txt changes)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn==23.0.0

# Copy entire project
COPY . .

# ── Build-time env vars ───────────────────────────────────────────────────────
# Needed so collectstatic can import settings without a real DB or secret key.
# These values are ONLY used during docker build — runtime reads from .env file.
ENV DJANGO_SETTINGS_MODULE=attendance_project.settings \
    SECRET_KEY=build-time-dummy-key-not-used-in-production \
    DATABASE_URL=sqlite:////tmp/build.db \
    DEBUG=False

# Collect static files — WhiteNoise serves them directly from Django/Gunicorn
# STATIC_ROOT = /app/attendance_project/staticfiles  (set in settings.py)
RUN python attendance_project/manage.py collectstatic --noinput

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/ || exit 1

# Gunicorn: chdir into attendance_project/ so Python finds attendance_project.wsgi
# which maps to /app/attendance_project/attendance_project/wsgi.py
CMD ["gunicorn", \
     "--chdir", "attendance_project", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "3", \
     "--timeout", "120", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "attendance_project.wsgi:application"]
