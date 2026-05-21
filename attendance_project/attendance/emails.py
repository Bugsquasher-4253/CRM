"""
Email notification utilities for Crefio.

All functions are fire-and-forget: email failures are logged but never
raise exceptions so the main request flow is never interrupted.

Admin notifications go to EVERY staff user who has an email address set.
"""

import logging
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags

logger = logging.getLogger(__name__)


# ─── INTERNAL HELPERS ───────────────────────────────────────────────────────

def _send(subject: str, to: str, template: str, context: dict) -> bool:
    """Render template and send as HTML + plain-text email. Fails silently."""
    if not to:
        logger.warning("Email skipped – recipient empty (subject: %s)", subject)
        return False
    try:
        html_body = render_to_string(template, context)
        text_body = strip_tags(html_body)
        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[to],
        )
        msg.attach_alternative(html_body, "text/html")
        msg.send(fail_silently=False)
        logger.info("Email sent → %s | %s", to, subject)
        return True
    except Exception as exc:
        logger.error("Email send failed → %s | %s | %s", to, subject, exc)
        return False


def _get_all_admin_emails() -> list[str]:
    """
    Return email addresses of every active staff user who has one set.
    This is the source of truth — no hardcoded env var needed.
    """
    from django.contrib.auth.models import User
    return list(
        User.objects.filter(is_staff=True, is_active=True)
                    .exclude(email='')
                    .values_list('email', flat=True)
    )


def _send_to_all_admins(subject: str, template: str, context: dict) -> int:
    """Send the same email to every admin. Returns count of successful sends."""
    admin_emails = _get_all_admin_emails()
    if not admin_emails:
        logger.warning("No admin emails found in DB – notification skipped (subject: %s)", subject)
        return 0
    sent = sum(_send(subject, email, template, context) for email in admin_emails)
    logger.info("Admin notification sent to %d/%d admins | %s", sent, len(admin_emails), subject)
    return sent


# ─── LEAVE NOTIFICATIONS ────────────────────────────────────────────────────

def notify_admin_leave_applied(leave) -> int:
    """Notify ALL admins when an employee submits a new leave request."""
    context = {
        'leave': leave,
        'employee': leave.employee,
        'app_name': 'Crefio',
    }
    return _send_to_all_admins(
        subject=f"[Crefio] New Leave Request – {leave.employee.user.get_full_name()}",
        template='attendance/emails/leave_applied.html',
        context=context,
    )


def notify_employee_leave_decision(leave) -> bool:
    """Notify the employee when their leave is approved or rejected."""
    employee_email = leave.employee.user.email
    if not employee_email:
        return False
    context = {
        'leave': leave,
        'employee': leave.employee,
        'app_name': 'Crefio',
        'approved': leave.status == 'approved',
    }
    status_label = 'Approved' if leave.status == 'approved' else 'Rejected'
    return _send(
        subject=f"[Crefio] Your Leave Request has been {status_label}",
        to=employee_email,
        template='attendance/emails/leave_decision.html',
        context=context,
    )


# ─── TICKET NOTIFICATIONS ───────────────────────────────────────────────────

def notify_admin_ticket_raised(ticket) -> int:
    """Notify ALL admins when an employee opens a new support ticket."""
    context = {
        'ticket': ticket,
        'employee': ticket.employee,
        'app_name': 'Crefio',
    }
    return _send_to_all_admins(
        subject=f"[Crefio] New Support Ticket #{ticket.id} – {ticket.subject}",
        template='attendance/emails/ticket_raised.html',
        context=context,
    )


def notify_employee_ticket_updated(ticket) -> bool:
    """Notify the employee when admin updates their ticket."""
    employee_email = ticket.employee.user.email
    if not employee_email:
        return False
    context = {
        'ticket': ticket,
        'employee': ticket.employee,
        'app_name': 'Crefio',
        'resolved': ticket.status == 'resolved',
    }
    return _send(
        subject=f"[Crefio] Ticket #{ticket.id} Update – {ticket.get_status_display()}",
        to=employee_email,
        template='attendance/emails/ticket_updated.html',
        context=context,
    )


def send_test_email(to: str) -> bool:
    """Send a test email to verify SMTP is working."""
    return _send(
        subject="[Crefio] ✅ Email Test – Setup Working",
        to=to,
        template='attendance/emails/test_email.html',
        context={'app_name': 'Crefio', 'recipient': to},
    )
