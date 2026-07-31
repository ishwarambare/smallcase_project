import django
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'smallcase_project.settings')
django.setup()

from django.core.mail import send_mail
from django.conf import settings


send_mail(
    subject='Test Email from Django The new one ',
    message='This is a test email sent from Django using Gmail SMTP.',
    from_email=settings.DEFAULT_FROM_EMAIL,
    recipient_list=['theeartharchive0@gmail.com'],
    fail_silently=False,
)