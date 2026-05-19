import os
import sys

# Add the Django project folder to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'attendance_project'))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'attendance_project.settings')

from django.core.wsgi import get_wsgi_application

app = get_wsgi_application()
