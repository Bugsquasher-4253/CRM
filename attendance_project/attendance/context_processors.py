from .models import AttendanceCorrectionRequest, LeaveRequest, Reimbursement, SupportTicket


def panel_context(request):
    if not request.user.is_authenticated:
        return {}

    panel_mode = request.session.get("panel_mode", "admin") if request.user.is_staff else "employee"

    context = {"panel_mode": panel_mode}

    if request.user.is_staff and panel_mode == "admin":
        context["pending_leaves_count"] = LeaveRequest.objects.filter(status="pending").count()
        context["open_tickets_count"] = SupportTicket.objects.filter(status="open").count()
        context["pending_corrections_count"] = AttendanceCorrectionRequest.objects.filter(status="pending").count()
        context["pending_reimbursements_count"] = Reimbursement.objects.filter(status="pending").count()

    return context
