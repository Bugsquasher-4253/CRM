import datetime

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


class Department(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Employee(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="employee")
    employee_id = models.CharField(max_length=20, unique=True)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True)
    phone = models.CharField(max_length=15, blank=True)
    designation = models.CharField(max_length=100)
    date_joined = models.DateField(default=timezone.now)
    profile_photo = models.ImageField(upload_to="profiles/", blank=True, null=True)
    aadhaar_card = models.FileField(upload_to="documents/aadhaar/", blank=True, null=True)
    pan_card = models.FileField(upload_to="documents/pan/", blank=True, null=True)
    is_active = models.BooleanField(default=True)
    has_seen_document_reminder = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.employee_id} - {self.user.get_full_name()}"

    def get_today_attendance(self):
        today = timezone.now().date()
        try:
            return AttendanceRecord.objects.get(employee=self, date=today)
        except AttendanceRecord.DoesNotExist:
            return None


class AttendanceRecord(models.Model):
    STATUS_CHOICES = [
        ("present", "Present"),
        ("absent", "Absent"),
        ("half_day", "Half Day"),
        ("leave", "On Leave"),
    ]

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="attendance_records")
    date = models.DateField(default=timezone.now)
    check_in_time = models.TimeField(null=True, blank=True)
    check_out_time = models.TimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="present")
    total_hours = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ["employee", "date"]
        ordering = ["-date", "-check_in_time"]

    def __str__(self):
        return f"{self.employee} - {self.date}"

    def calculate_hours(self):
        """
        Recalculate total_hours and auto-set status based on business rules:
          - No check-in            → absent (caller should handle; record shouldn't exist)
          - Check-in, no check-out → present (full day credit; hours remain None)
          - Check-in + check-out,
              hours >= 5           → present (full day)
              hours <  5           → half_day
        Handles edge case where check-out is before check-in (midnight cross or bad entry)
        by treating hours as 0 (→ half_day).
        """
        if self.check_in_time and self.check_out_time:
            check_in = datetime.datetime.combine(self.date, self.check_in_time)
            check_out = datetime.datetime.combine(self.date, self.check_out_time)
            # Midnight crossover: checkout is next calendar day (e.g. in 10:56 PM, out 01:02 AM)
            if check_out <= check_in:
                check_out += datetime.timedelta(days=1)
            duration = check_out - check_in
            hours = duration.total_seconds() / 3600
            self.total_hours = round(hours, 2)
            # ≥5 hours → full day present; <5 → half day
            if hours >= 5:
                self.status = "present"
            else:
                self.status = "half_day"
        elif self.check_in_time and not self.check_out_time:
            # Checked in but forgot to check out → still present (full day)
            self.total_hours = None
            self.status = "present"
        # If somehow neither time exists, leave status as-is (absent / leave set externally)
        self.save()
        return self.total_hours


class LeaveRequest(models.Model):
    LEAVE_TYPE_CHOICES = [
        ("full_day", "Full Day Leave"),
        ("half_day", "Half Day Leave"),
        ("sick", "Sick Leave"),
        ("casual", "Casual Leave"),
        ("emergency", "Emergency Leave"),
    ]
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="leave_requests")
    leave_type = models.CharField(max_length=20, choices=LEAVE_TYPE_CHOICES)
    from_date = models.DateField()
    to_date = models.DateField()
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    admin_note = models.TextField(blank=True)
    applied_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-applied_on"]

    def __str__(self):
        return f"{self.employee} - {self.leave_type} ({self.from_date})"

    @property
    def total_days(self):
        import datetime as _dt

        total, cur = 0, self.from_date
        while cur <= self.to_date:
            if cur.weekday() != 6:  # skip Sunday
                total += 1
            cur += _dt.timedelta(days=1)
        return total


class SupportTicket(models.Model):
    PRIORITY_CHOICES = [
        ("low", "Low"),
        ("medium", "Medium"),
        ("high", "High"),
        ("critical", "Critical"),
    ]
    STATUS_CHOICES = [
        ("open", "Open"),
        ("in_progress", "In Progress"),
        ("waiting", "Waiting for Response"),
        ("resolved", "Resolved"),
        ("closed", "Closed"),
    ]
    CATEGORY_CHOICES = [
        ("technical", "Technical Issue"),
        ("hr", "HR"),
        ("payroll", "Payroll"),
        ("leave", "Leave"),
        ("general", "General Query"),
        ("other", "Other"),
    ]

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="tickets")
    subject = models.CharField(max_length=200)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default="general")
    description = models.TextField()
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default="medium")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="open")
    admin_response = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"#{self.id} - {self.subject} ({self.employee})"


class AttendanceCorrectionRequest(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="correction_requests")
    date = models.DateField()
    requested_check_in = models.TimeField(null=True, blank=True)
    requested_check_out = models.TimeField(null=True, blank=True)
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    admin_note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.employee} - {self.date} ({self.status})"


class EmployeeSalaryStructure(models.Model):
    """
    Base salary for an employee. One row per revision.
    The row with the latest effective_from <= payroll month is used.
    Historical payroll records are never changed when salary is updated.
    """

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="salary_structures")
    basic_salary = models.DecimalField(max_digits=10, decimal_places=2)
    allowances = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    effective_from = models.DateField(help_text="First day of the month this salary takes effect")
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-effective_from"]
        unique_together = ["employee", "effective_from"]

    def __str__(self):
        import calendar

        return (
            f"{self.employee.user.get_full_name()} — "
            f"₹{self.basic_salary} from "
            f"{calendar.month_name[self.effective_from.month]} {self.effective_from.year}"
        )

    @classmethod
    def active_for(cls, employee, month: int, year: int):
        """Return the salary structure effective for the given month/year, or None."""
        import datetime as _dt

        target = _dt.date(year, month, 1)
        return cls.objects.filter(
            employee=employee, effective_from__lte=target
        ).first()  # ordering is -effective_from → first = most recent applicable


class Reimbursement(models.Model):
    CATEGORY_CHOICES = [
        ("travel", "Travel"),
        ("food", "Food & Meals"),
        ("internet", "Internet"),
        ("office_supplies", "Office Supplies"),
        ("client_meeting", "Client Meeting"),
        ("accommodation", "Accommodation"),
        ("other", "Other"),
    ]
    STATUS_CHOICES = [
        ("pending", "Pending Approval"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]
    PAYMENT_METHOD_CHOICES = [
        ("cash", "Cash"),
        ("upi", "UPI"),
        ("credit_card", "Credit Card"),
        ("debit_card", "Debit Card"),
        ("bank_transfer", "Bank Transfer"),
        ("other", "Other"),
    ]

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="reimbursements")
    title = models.CharField(max_length=200)
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    expense_date = models.DateField()
    reason = models.TextField()
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    admin_remarks = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="reviewed_reimbursements"
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-submitted_at"]

    def __str__(self):
        return f"#{self.id} - {self.title} ({self.employee})"


class ReimbursementAttachment(models.Model):
    reimbursement = models.ForeignKey(Reimbursement, on_delete=models.CASCADE, related_name="attachments")
    file = models.FileField(upload_to="reimbursements/%Y/%m/")
    filename = models.CharField(max_length=255)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.filename

    @property
    def is_image(self):
        ext = self.filename.rsplit(".", 1)[-1].lower() if "." in self.filename else ""
        return ext in ("jpg", "jpeg", "png", "gif", "webp")

    @property
    def is_pdf(self):
        return self.filename.lower().endswith(".pdf")


class SalaryRecord(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="salary_records")
    month = models.IntegerField()
    year = models.IntegerField()
    basic_salary = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    allowances = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    deductions = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    net_salary = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_paid = models.BooleanField(default=False)
    absent_days = models.IntegerField(default=0)
    half_days = models.IntegerField(default=0)
    paid_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ["employee", "month", "year"]
        ordering = ["-year", "-month"]

    def __str__(self):
        import calendar

        return f"{self.employee.user.get_full_name()} - {calendar.month_name[self.month]} {self.year}"

    @property
    def daily_rate(self):
        return float(self.basic_salary) / 30.4 if self.basic_salary else 0

    def save(self, *args, **kwargs):
        # View pre-computes net/deductions with the full formula and sets _skip_auto_calc.
        # Fallback (e.g. admin panel): deduct absent + half only.
        if not getattr(self, "_skip_auto_calc", False):
            rate = self.daily_rate
            self.deductions = round(self.absent_days * rate + self.half_days * rate * 0.5, 2)
            self.net_salary = round(max(0.0, float(self.basic_salary) + float(self.allowances) - self.deductions), 2)
        super().save(*args, **kwargs)
