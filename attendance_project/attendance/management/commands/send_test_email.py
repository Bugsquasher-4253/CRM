from django.core.management.base import BaseCommand
from attendance.emails import send_test_email


class Command(BaseCommand):
    help = "Send a test email to verify SMTP configuration"

    def add_arguments(self, parser):
        parser.add_argument("email", type=str, help="Recipient email address")

    def handle(self, *args, **options):
        to = options["email"]
        self.stdout.write(f"Sending test email to {to} ...")
        ok = send_test_email(to)
        if ok:
            self.stdout.write(self.style.SUCCESS(f"✅ Email sent successfully to {to}"))
        else:
            self.stdout.write(self.style.ERROR(f"❌ Failed to send email to {to} — check your SMTP settings"))
