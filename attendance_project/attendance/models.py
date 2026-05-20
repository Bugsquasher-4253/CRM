from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import datetime


class Department(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Employee(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='employee')
    employee_id = models.CharField(max_length=20, unique=True)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True)
    phone = models.CharField(max_length=15, blank=True)
    designation = models.CharField(max_length=100)
    date_joined = models.DateField(default=timezone.now)
    profile_photo = models.ImageField(upload_to='profiles/', blank=True, null=True)
    aadhaar_card = models.FileField(upload_to='documents/aadhaar/', blank=True, null=True)
    pan_card = models.FileField(upload_to='documents/pan/', blank=True, null=True)
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
        ('present', 'Present'),
        ('absent', 'Absent'),
        ('half_day', 'Half Day'),
        ('leave', 'On Leave'),
    ]

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='attendance_records')
    date = models.DateField(default=timezone.now)
    check_in_time = models.TimeField(null=True, blank=True)
    check_out_time = models.TimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='present')
    total_hours = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['employee', 'date']
        ordering = ['-date', '-check_in_time']

    def __str__(self):
        return f"{self.employee} - {self.date}"

    def calculate_hours(self):
        if self.check_in_time and self.check_out_time:
            check_in = datetime.datetime.combine(self.date, self.check_in_time)
            check_out = datetime.datetime.combine(self.date, self.check_out_time)
            duration = check_out - check_in
            hours = duration.total_seconds() / 3600
            self.total_hours = round(hours, 2)
            self.save()
            return self.total_hours
        return None


class LeaveRequest(models.Model):
    LEAVE_TYPE_CHOICES = [
        ('full_day', 'Full Day Leave'),
        ('half_day', 'Half Day Leave'),
        ('sick', 'Sick Leave'),
        ('casual', 'Casual Leave'),
        ('emergency', 'Emergency Leave'),
    ]
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='leave_requests')
    leave_type = models.CharField(max_length=20, choices=LEAVE_TYPE_CHOICES)
    from_date = models.DateField()
    to_date = models.DateField()
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    admin_note = models.TextField(blank=True)
    applied_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-applied_on']

    def __str__(self):
        return f"{self.employee} - {self.leave_type} ({self.from_date})"

    @property
    def total_days(self):
        delta = self.to_date - self.from_date
        return delta.days + 1


class SupportTicket(models.Model):
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
    ]
    STATUS_CHOICES = [
        ('open', 'Open'),
        ('in_progress', 'In Progress'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed'),
    ]

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='tickets')
    subject = models.CharField(max_length=200)
    description = models.TextField()
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='medium')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    admin_response = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"#{self.id} - {self.subject} ({self.employee})"


class AttendanceCorrectionRequest(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    employee            = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='correction_requests')
    date                = models.DateField()
    requested_check_in  = models.TimeField(null=True, blank=True)
    requested_check_out = models.TimeField(null=True, blank=True)
    reason              = models.TextField()
    status              = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    admin_note          = models.TextField(blank=True)
    created_at          = models.DateTimeField(auto_now_add=True)
    updated_at          = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.employee} - {self.date} ({self.status})"


class SalaryRecord(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='salary_records')
    month = models.IntegerField()
    year = models.IntegerField()
    basic_salary = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    allowances = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    deductions = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    net_salary = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_paid = models.BooleanField(default=False)
    paid_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['employee', 'month', 'year']
        ordering = ['-year', '-month']

    def __str__(self):
        import calendar
        return f"{self.employee.user.get_full_name()} - {calendar.month_name[self.month]} {self.year}"

    def save(self, *args, **kwargs):
        self.net_salary = self.basic_salary + self.allowances - self.deductions
        super().save(*args, **kwargs)
