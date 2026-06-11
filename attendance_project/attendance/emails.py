"""
Email notification utilities for Crefio.

All functions are fire-and-forget: failures are logged but never raise,
so the main request flow is never interrupted.

Admin notifications go to EVERY staff user who has an email address.
Admin emails include one-click Approve / Reject buttons backed by signed
tokens (7-day expiry) — admin can act directly from their inbox.
"""

import logging

from django.conf import settings
from django.core import signing
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags

logger = logging.getLogger(__name__)

_TOKEN_SALT = "crefio-email-action"
_TOKEN_MAX_AGE = 7 * 24 * 3600  # 7 days in seconds


# ─── INTERNAL HELPERS ────────────────────────────────────────────────────────


def _send(subject: str, to: str, template: str, context: dict) -> bool:
    if not to:
        logger.warning("Email skipped – empty recipient (subject: %s)", subject)
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
    from django.contrib.auth.models import User

    db_emails = set(
        User.objects.filter(is_staff=True, is_active=True).exclude(email="").values_list("email", flat=True)
    )
    env_email = getattr(settings, "ADMIN_NOTIFICATION_EMAIL", "").strip()
    if env_email:
        db_emails.add(env_email)
    return list(db_emails)


def _send_to_all_admins(subject: str, template: str, context: dict) -> int:
    admin_emails = _get_all_admin_emails()
    if not admin_emails:
        logger.warning("No admin emails – skipped (subject: %s)", subject)
        return 0
    sent = sum(_send(subject, email, template, context) for email in admin_emails)
    logger.info("Admin notification %d/%d | %s", sent, len(admin_emails), subject)
    return sent


# ─── TOKEN HELPERS ────────────────────────────────────────────────────────────


def _make_token(obj_type: str, obj_id: int, action: str) -> str:
    return signing.dumps(
        {"t": obj_type, "id": obj_id, "a": action},
        salt=_TOKEN_SALT,
        compress=True,
    )


def _action_url(token: str) -> str:
    site = getattr(settings, "SITE_URL", "http://127.0.0.1:8000").rstrip("/")
    return f"{site}/ea/{token}/"


def decode_action_token(token: str) -> dict:
    """Decode and verify a signed action token. Raises signing exceptions on failure."""
    return signing.loads(token, salt=_TOKEN_SALT, max_age=_TOKEN_MAX_AGE)


# ─── LEAVE NOTIFICATIONS ─────────────────────────────────────────────────────


def notify_admin_leave_applied(leave) -> int:
    context = {
        "leave": leave,
        "employee": leave.employee,
        "app_name": "Crefio",
        "approve_url": _action_url(_make_token("leave", leave.id, "approved")),
        "reject_url": _action_url(_make_token("leave", leave.id, "rejected")),
    }
    return _send_to_all_admins(
        subject=f"[Crefio] Leave Request — {leave.employee.user.get_full_name()} · Action Required",
        template="attendance/emails/leave_applied.html",
        context=context,
    )


def notify_employee_leave_decision(leave) -> bool:
    employee_email = leave.employee.user.email
    if not employee_email:
        return False
    context = {
        "leave": leave,
        "employee": leave.employee,
        "app_name": "Crefio",
        "approved": leave.status == "approved",
    }
    status_label = "Approved" if leave.status == "approved" else "Rejected"
    return _send(
        subject=f"[Crefio] Your Leave Request has been {status_label}",
        to=employee_email,
        template="attendance/emails/leave_decision.html",
        context=context,
    )


# ─── TICKET NOTIFICATIONS ────────────────────────────────────────────────────


def notify_admin_ticket_raised(ticket) -> int:
    context = {
        "ticket": ticket,
        "employee": ticket.employee,
        "app_name": "Crefio",
        "resolve_url": _action_url(_make_token("ticket", ticket.id, "resolved")),
        "in_progress_url": _action_url(_make_token("ticket", ticket.id, "in_progress")),
    }
    return _send_to_all_admins(
        subject=f"[Crefio] Ticket #{ticket.id} — {ticket.subject} · Action Required",
        template="attendance/emails/ticket_raised.html",
        context=context,
    )


def notify_employee_ticket_updated(ticket) -> bool:
    employee_email = ticket.employee.user.email
    if not employee_email:
        return False
    context = {
        "ticket": ticket,
        "employee": ticket.employee,
        "app_name": "Crefio",
        "resolved": ticket.status == "resolved",
    }
    return _send(
        subject=f"[Crefio] Ticket #{ticket.id} Update — {ticket.get_status_display()}",
        to=employee_email,
        template="attendance/emails/ticket_updated.html",
        context=context,
    )


# ─── CORRECTION NOTIFICATIONS ────────────────────────────────────────────────


def notify_admin_correction_raised(correction) -> int:
    context = {
        "correction": correction,
        "employee": correction.employee,
        "app_name": "Crefio",
        "approve_url": _action_url(_make_token("correction", correction.id, "approved")),
        "reject_url": _action_url(_make_token("correction", correction.id, "rejected")),
    }
    return _send_to_all_admins(
        subject=f"[Crefio] Correction Request — {correction.employee.user.get_full_name()} · Action Required",
        template="attendance/emails/correction_raised.html",
        context=context,
    )


def notify_employee_correction_decision(correction) -> bool:
    employee_email = correction.employee.user.email
    if not employee_email:
        return False
    context = {
        "correction": correction,
        "employee": correction.employee,
        "app_name": "Crefio",
        "approved": correction.status == "approved",
    }
    status_label = "Approved" if correction.status == "approved" else "Rejected"
    return _send(
        subject=f"[Crefio] Your Attendance Correction has been {status_label}",
        to=employee_email,
        template="attendance/emails/correction_decision.html",
        context=context,
    )


# ─── REIMBURSEMENT NOTIFICATIONS ────────────────────────────────────────────


def notify_admin_reimbursement_submitted(reimbursement) -> int:
    context = {
        "reimbursement": reimbursement,
        "employee": reimbursement.employee,
        "app_name": "Crefio",
        "approve_url": _action_url(_make_token("reimbursement", reimbursement.id, "approved")),
        "reject_url": _action_url(_make_token("reimbursement", reimbursement.id, "rejected")),
    }
    return _send_to_all_admins(
        subject=f"[Crefio] Reimbursement #{reimbursement.id} — {reimbursement.employee.user.get_full_name()} · Action Required",
        template="attendance/emails/reimbursement_admin_notify.html",
        context=context,
    )


def notify_employee_reimbursement_submitted(reimbursement) -> bool:
    employee_email = reimbursement.employee.user.email
    if not employee_email:
        return False
    context = {
        "reimbursement": reimbursement,
        "employee": reimbursement.employee,
        "app_name": "Crefio",
    }
    return _send(
        subject=f"[Crefio] Reimbursement Request #{reimbursement.id} Submitted",
        to=employee_email,
        template="attendance/emails/reimbursement_submitted.html",
        context=context,
    )


def notify_employee_reimbursement_decision(reimbursement) -> bool:
    employee_email = reimbursement.employee.user.email
    if not employee_email:
        return False
    context = {
        "reimbursement": reimbursement,
        "employee": reimbursement.employee,
        "app_name": "Crefio",
        "approved": reimbursement.status == "approved",
    }
    status_label = "Approved" if reimbursement.status == "approved" else "Rejected"
    return _send(
        subject=f"[Crefio] Reimbursement #{reimbursement.id} {status_label} — {reimbursement.title}",
        to=employee_email,
        template="attendance/emails/reimbursement_decision.html",
        context=context,
    )


# ─── TEST EMAIL ──────────────────────────────────────────────────────────────


def send_test_email(to: str) -> bool:
    return _send(
        subject="[Crefio] Email Test — Setup Working",
        to=to,
        template="attendance/emails/test_email.html",
        context={"app_name": "Crefio", "recipient": to},
    )
