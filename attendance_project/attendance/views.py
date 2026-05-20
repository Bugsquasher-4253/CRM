from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.contrib import messages
from django.utils import timezone
from django.db import transaction, IntegrityError
from django.db.models import Q, Count
from .models import Employee, AttendanceRecord, Department, LeaveRequest, SupportTicket, SalaryRecord, AttendanceCorrectionRequest
from .forms import (
    LoginForm, EmployeeForm, UserForm,
    LeaveRequestForm, SupportTicketForm,
    AdminLeaveResponseForm, AdminTicketResponseForm,
    EmployeeProfileEditForm, SalaryForm, DepartmentForm,
    AdminEmployeeEditForm, AttendanceRecordForm, AdminPasswordChangeForm,
    AttendanceCorrectionForm, AdminCorrectionResponseForm,
)
import datetime


def is_admin(user):
    return user.is_staff or user.is_superuser


def generate_employee_id():
    import re
    # select_for_update locks the last row so two concurrent adds get different IDs
    with transaction.atomic():
        last = Employee.objects.select_for_update().order_by('id').last()
        if last:
            match = re.search(r'\d+$', last.employee_id)
            num = int(match.group()) + 1 if match else Employee.objects.count() + 1
        else:
            num = 1
        return f"CRF{num:03d}"


def get_panel_mode(request):
    """Returns current panel mode for a staff user."""
    if request.user.is_staff:
        return request.session.get('panel_mode', 'admin')
    return 'employee'


# ─── AUTH VIEWS ─────────────────────────────────────────────────────────────

def login_view(request):
    if request.user.is_authenticated:
        if request.user.is_staff and get_panel_mode(request) == 'admin':
            return redirect('admin_dashboard')
        return redirect('dashboard')

    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            email    = form.cleaned_data['email'].strip().lower()
            password = form.cleaned_data['password']
            user = None
            try:
                user_obj = User.objects.get(email__iexact=email)
                user = authenticate(request, username=user_obj.username, password=password)
            except User.DoesNotExist:
                pass
            except User.MultipleObjectsReturned:
                messages.error(request, 'Multiple accounts found with this email. Contact admin.')
                user = None
            if user is not None:
                login(request, user)
                if user.is_staff:
                    request.session['panel_mode'] = 'admin'
                    return redirect('admin_dashboard')
                return redirect('dashboard')
            else:
                messages.error(request, 'Invalid email or password.')
    else:
        form = LoginForm()

    return render(request, 'attendance/login.html', {'form': form})


def logout_view(request):
    logout(request)
    return redirect('login')


# ─── PANEL SWITCHER (Admin only) ────────────────────────────────────────────

@login_required
@user_passes_test(is_admin)
def switch_panel(request):
    """Lets admin switch between Admin Panel and Employee Panel."""
    current = get_panel_mode(request)

    if current == 'admin':
        try:
            request.user.employee
            request.session['panel_mode'] = 'employee'
            messages.info(request, 'Switched to Employee View.')
            return redirect('dashboard')
        except Employee.DoesNotExist:
            messages.warning(
                request,
                'You need an Employee Profile to use the Employee Panel. '
                'Go to Django Admin (/admin/) and create an Employee entry linked to your user account.'
            )
            return redirect('admin_dashboard')
    else:
        request.session['panel_mode'] = 'admin'
        messages.info(request, 'Switched to Admin Panel.')
        return redirect('admin_dashboard')


# ─── EMPLOYEE DASHBOARD ──────────────────────────────────────────────────────

@login_required
def dashboard(request):
    # Staff in admin mode → push them back to admin panel
    if request.user.is_staff and get_panel_mode(request) == 'admin':
        return redirect('admin_dashboard')

    try:
        employee = request.user.employee
    except Employee.DoesNotExist:
        messages.error(request, 'Employee profile not found. Contact admin.')
        logout(request)
        return redirect('login')

    today = timezone.now().date()
    today_attendance = employee.get_today_attendance()

    week_ago = today - datetime.timedelta(days=7)
    recent_attendance = AttendanceRecord.objects.filter(
        employee=employee, date__gte=week_ago
    ).order_by('-date')

    monthly_records = AttendanceRecord.objects.filter(
        employee=employee,
        date__month=today.month,
        date__year=today.year
    )

    show_doc_reminder = not employee.has_seen_document_reminder

    context = {
        'employee': employee,
        'today': today,
        'today_attendance': today_attendance,
        'recent_attendance': recent_attendance,
        'present_days': monthly_records.filter(status='present').count(),
        'absent_days': monthly_records.filter(status='absent').count(),
        'leave_days': monthly_records.filter(status='leave').count(),
        'show_doc_reminder': show_doc_reminder,
    }
    return render(request, 'attendance/dashboard.html', context)


# ─── DISMISS DOCUMENT REMINDER ───────────────────────────────────────────────

@login_required
def dismiss_document_reminder(request):
    from django.http import JsonResponse
    if request.method == 'POST':
        try:
            request.user.employee.has_seen_document_reminder = True
            request.user.employee.save(update_fields=['has_seen_document_reminder'])
        except Employee.DoesNotExist:
            pass
    return JsonResponse({'ok': True})


# ─── ATTENDANCE ──────────────────────────────────────────────────────────────

@login_required
def check_in(request):
    try:
        employee = request.user.employee
    except Employee.DoesNotExist:
        return redirect('dashboard')

    today = timezone.now().date()
    now_time = timezone.localtime(timezone.now()).time()

    try:
        with transaction.atomic():
            attendance, created = AttendanceRecord.objects.get_or_create(
                employee=employee,
                date=today,
                defaults={'check_in_time': now_time, 'status': 'present'}
            )
    except IntegrityError:
        # Two simultaneous requests — fetch what was just created
        attendance = AttendanceRecord.objects.get(employee=employee, date=today)
        created = False

    if not created and attendance.check_in_time:
        messages.warning(request, f'Already checked in at {attendance.check_in_time.strftime("%I:%M %p")}')
    elif not created and not attendance.check_in_time:
        with transaction.atomic():
            attendance.check_in_time = now_time
            attendance.status = 'present'
            attendance.save()
        messages.success(request, f'Check-in successful at {now_time.strftime("%I:%M %p")}')
    else:
        messages.success(request, f'Check-in successful at {now_time.strftime("%I:%M %p")}')

    return redirect('dashboard')


@login_required
def check_out(request):
    try:
        employee = request.user.employee
    except Employee.DoesNotExist:
        return redirect('dashboard')

    today = timezone.now().date()
    now_time = timezone.localtime(timezone.now()).time()

    try:
        with transaction.atomic():
            attendance = AttendanceRecord.objects.select_for_update().get(
                employee=employee, date=today
            )
            if not attendance.check_in_time:
                messages.error(request, 'You have not checked in today.')
            elif attendance.check_out_time:
                messages.warning(request, f'Already checked out at {attendance.check_out_time.strftime("%I:%M %p")}')
            else:
                attendance.check_out_time = now_time
                attendance.save()
                attendance.calculate_hours()
                messages.success(
                    request,
                    f'Check-out at {now_time.strftime("%I:%M %p")}. Total: {attendance.total_hours} hrs'
                )
    except AttendanceRecord.DoesNotExist:
        messages.error(request, 'No check-in found for today. Please check in first.')

    return redirect('dashboard')


@login_required
def my_attendance(request):
    try:
        employee = request.user.employee
    except Employee.DoesNotExist:
        return redirect('login')

    import calendar
    month = int(request.GET.get('month', timezone.now().month))
    year = int(request.GET.get('year', timezone.now().year))

    records = AttendanceRecord.objects.filter(
        employee=employee, date__month=month, date__year=year
    ).order_by('-date')

    context = {
        'employee': employee,
        'records': records,
        'month': month,
        'year': year,
        'month_name': calendar.month_name[month],
        'present': records.filter(status='present').count(),
        'absent': records.filter(status='absent').count(),
        'leave': records.filter(status='leave').count(),
        'months': [(i, calendar.month_name[i]) for i in range(1, 13)],
        'years': range(2023, timezone.now().year + 1),
    }
    return render(request, 'attendance/my_attendance.html', context)


# ─── EMPLOYEE PROFILE EDIT ───────────────────────────────────────────────────

@login_required
def edit_profile(request):
    try:
        employee = request.user.employee
    except Employee.DoesNotExist:
        messages.error(request, 'No employee profile found.')
        return redirect('dashboard')

    if request.method == 'POST':
        form = EmployeeProfileEditForm(request.POST, request.FILES)
        if form.is_valid():
            user = request.user
            user.first_name = form.cleaned_data['first_name']
            user.last_name = form.cleaned_data['last_name']
            user.email = form.cleaned_data['email']
            user.save()

            employee.phone = form.cleaned_data['phone']
            if form.cleaned_data.get('profile_photo'):
                employee.profile_photo = form.cleaned_data['profile_photo']
            if form.cleaned_data.get('aadhaar_card'):
                employee.aadhaar_card = form.cleaned_data['aadhaar_card']
            if form.cleaned_data.get('pan_card'):
                employee.pan_card = form.cleaned_data['pan_card']
            try:
                employee.save()
            except OSError:
                employee.profile_photo = None
                employee.aadhaar_card  = None
                employee.pan_card      = None
                employee.save()

            messages.success(request, 'Profile updated successfully!')
            return redirect('edit_profile')
    else:
        form = EmployeeProfileEditForm(initial={
            'first_name': request.user.first_name,
            'last_name': request.user.last_name,
            'email': request.user.email,
            'phone': employee.phone,
        })

    return render(request, 'attendance/edit_profile.html', {
        'form': form,
        'employee': employee,
    })


# ─── ADMIN DASHBOARD ─────────────────────────────────────────────────────────

@login_required
@user_passes_test(is_admin)
def admin_dashboard(request):
    # If admin switched to employee mode, redirect them to employee panel
    if get_panel_mode(request) == 'employee':
        return redirect('dashboard')

    today = timezone.now().date()
    total_employees = Employee.objects.filter(is_active=True).count()
    today_present = AttendanceRecord.objects.filter(date=today, status='present').count()

    checked_in_now = AttendanceRecord.objects.filter(
        date=today, check_in_time__isnull=False, check_out_time__isnull=True
    ).select_related('employee__user')

    recent_activity = AttendanceRecord.objects.filter(
        date=today
    ).select_related('employee__user').order_by('-check_in_time')[:10]

    context = {
        'total_employees': total_employees,
        'today_present': today_present,
        'today_absent': total_employees - today_present,
        'checked_in_now': checked_in_now,
        'recent_activity': recent_activity,
        'today': today,
    }
    return render(request, 'attendance/admin_dashboard.html', context)


# ─── ADMIN EMPLOYEE MANAGEMENT ───────────────────────────────────────────────

@login_required
@user_passes_test(is_admin)
def manage_employees(request):
    employees = Employee.objects.filter(is_active=True).select_related('user', 'department')
    departments = Department.objects.all()
    search = request.GET.get('search', '')
    dept_filter = request.GET.get('department', '')

    if search:
        employees = employees.filter(
            Q(user__first_name__icontains=search) |
            Q(user__last_name__icontains=search) |
            Q(employee_id__icontains=search) |
            Q(designation__icontains=search)
        )
    if dept_filter:
        employees = employees.filter(department__id=dept_filter)

    return render(request, 'attendance/employees.html', {
        'employees': employees,
        'departments': departments,
        'search': search,
    })


@login_required
@user_passes_test(is_admin)
def view_employee_detail(request, emp_id):
    employee = get_object_or_404(Employee, id=emp_id)
    recent_attendance = AttendanceRecord.objects.filter(employee=employee).order_by('-date')[:10]
    recent_leaves = LeaveRequest.objects.filter(employee=employee)[:5]
    recent_tickets = SupportTicket.objects.filter(employee=employee)[:5]

    return render(request, 'attendance/employee_detail.html', {
        'employee': employee,
        'recent_attendance': recent_attendance,
        'recent_leaves': recent_leaves,
        'recent_tickets': recent_tickets,
    })


@login_required
@user_passes_test(is_admin)
def add_employee(request):
    next_id = generate_employee_id()
    if request.method == 'POST':
        user_form = UserForm(request.POST)
        emp_form = EmployeeForm(request.POST, request.FILES)
        if user_form.is_valid() and emp_form.is_valid():
            try:
                with transaction.atomic():
                    user = user_form.save(commit=False)
                    user.set_password(user_form.cleaned_data['password'])
                    user.save()
                    employee = emp_form.save(commit=False)
                    employee.user = user
                    employee.employee_id = next_id
                    try:
                        employee.save()
                    except OSError:
                        # File system not writable (e.g. Vercel) — save without photo
                        employee.profile_photo = None
                        employee.save()
            except IntegrityError:
                messages.error(request, 'A duplicate was detected. Please try again.')
                return redirect('add_employee')
            messages.success(request, f'Employee {user.get_full_name()} added! Employee ID: {next_id}')
            return redirect('manage_employees')
        else:
            messages.error(request, 'Please fix the errors below.')
    else:
        user_form = UserForm()
        emp_form = EmployeeForm()

    return render(request, 'attendance/add_employee.html', {
        'user_form': user_form,
        'emp_form': emp_form,
        'next_employee_id': next_id,
    })


# ─── EMPLOYEE EDIT / ACTIONS (Admin) ─────────────────────────────────────────

@login_required
@user_passes_test(is_admin)
def edit_employee_admin(request, emp_id):
    employee = get_object_or_404(Employee, id=emp_id)
    user = employee.user

    if request.method == 'POST':
        form = AdminEmployeeEditForm(request.POST, request.FILES)
        if form.is_valid():
            user.first_name  = form.cleaned_data['first_name']
            user.last_name   = form.cleaned_data['last_name']
            user.email       = form.cleaned_data['email']
            user.username    = form.cleaned_data['username']
            user.is_active   = form.cleaned_data.get('is_active_user', False)
            user.save()

            employee.employee_id = form.cleaned_data['employee_id']
            employee.department  = form.cleaned_data['department']
            employee.designation = form.cleaned_data['designation']
            employee.phone       = form.cleaned_data['phone']
            employee.date_joined = form.cleaned_data['date_joined']
            if form.cleaned_data.get('profile_photo'):
                employee.profile_photo = form.cleaned_data['profile_photo']
            if form.cleaned_data.get('aadhaar_card'):
                employee.aadhaar_card = form.cleaned_data['aadhaar_card']
            if form.cleaned_data.get('pan_card'):
                employee.pan_card = form.cleaned_data['pan_card']
            try:
                employee.save()
            except OSError:
                employee.profile_photo = None
                employee.aadhaar_card  = None
                employee.pan_card      = None
                employee.save()

            messages.success(request, f'Employee {user.get_full_name()} updated successfully!')
            return redirect('employee_detail', emp_id=emp_id)
    else:
        form = AdminEmployeeEditForm(initial={
            'first_name':   user.first_name,
            'last_name':    user.last_name,
            'email':        user.email,
            'username':     user.username,
            'is_active_user': user.is_active,
            'employee_id':  employee.employee_id,
            'department':   employee.department,
            'designation':  employee.designation,
            'phone':        employee.phone,
            'date_joined':  employee.date_joined,
        })

    return render(request, 'attendance/edit_employee_admin.html', {
        'form': form,
        'employee': employee,
    })


@login_required
@user_passes_test(is_admin)
def toggle_employee_active(request, emp_id):
    employee = get_object_or_404(Employee, id=emp_id)
    if request.method == 'POST':
        employee.is_active = not employee.is_active
        employee.save()
        status = 'activated' if employee.is_active else 'deactivated'
        messages.success(request, f'{employee.user.get_full_name()} has been {status}.')
    return redirect('employee_detail', emp_id=emp_id)


@login_required
@user_passes_test(is_admin)
def toggle_employee_admin(request, emp_id):
    employee = get_object_or_404(Employee, id=emp_id)
    if request.method == 'POST':
        user = employee.user
        if user == request.user:
            messages.error(request, 'You cannot change your own admin status.')
            return redirect('employee_detail', emp_id=emp_id)
        if not user.email:
            messages.error(request, f'Set an email for {user.get_full_name()} first — they need it to log in.')
            return redirect('edit_employee_admin', emp_id=emp_id)
        user.is_staff = not user.is_staff
        user.save()
        action = 'granted admin access' if user.is_staff else 'revoked admin access'
        messages.success(request, f'{user.get_full_name()} has been {action}.')
    return redirect('employee_detail', emp_id=emp_id)


@login_required
@user_passes_test(is_admin)
def reset_employee_password(request, emp_id):
    employee = get_object_or_404(Employee, id=emp_id)
    if request.method == 'POST':
        form = AdminPasswordChangeForm(request.POST)
        if form.is_valid():
            employee.user.set_password(form.cleaned_data['new_password'])
            employee.user.save()
            messages.success(request, f'Password for {employee.user.get_full_name()} reset successfully!')
            return redirect('employee_detail', emp_id=emp_id)
    else:
        form = AdminPasswordChangeForm()

    return render(request, 'attendance/reset_employee_password.html', {
        'form': form,
        'employee': employee,
    })


# ─── ATTENDANCE RECORD MANAGEMENT (Admin) ────────────────────────────────────

@login_required
@user_passes_test(is_admin)
def admin_attendance_records(request):
    records = AttendanceRecord.objects.select_related(
        'employee__user', 'employee__department'
    ).order_by('-date', '-check_in_time')

    emp_filter    = request.GET.get('employee', '')
    date_filter   = request.GET.get('date', '')
    status_filter = request.GET.get('status', '')

    if emp_filter:
        records = records.filter(employee__id=emp_filter)
    if date_filter:
        try:
            records = records.filter(date=datetime.date.fromisoformat(date_filter))
        except ValueError:
            pass
    if status_filter:
        records = records.filter(status=status_filter)

    employees = Employee.objects.filter(is_active=True).select_related('user')
    total = records.count()

    return render(request, 'attendance/admin_attendance_records.html', {
        'records':       records[:200],
        'employees':     employees,
        'emp_filter':    emp_filter,
        'date_filter':   date_filter,
        'status_filter': status_filter,
        'total':         total,
        'status_choices': AttendanceRecord.STATUS_CHOICES,
    })


@login_required
@user_passes_test(is_admin)
def add_attendance_record(request):
    if request.method == 'POST':
        form = AttendanceRecordForm(request.POST)
        if form.is_valid():
            record = form.save()
            record.calculate_hours()
            messages.success(request, 'Attendance record added.')
            return redirect('admin_attendance_records')
    else:
        form = AttendanceRecordForm(initial={'date': timezone.now().date()})

    return render(request, 'attendance/add_edit_attendance.html', {
        'form': form,
        'title': 'Add Attendance Record',
        'is_edit': False,
    })


@login_required
@user_passes_test(is_admin)
def edit_attendance_record(request, record_id):
    record = get_object_or_404(AttendanceRecord, id=record_id)
    if request.method == 'POST':
        form = AttendanceRecordForm(request.POST, instance=record)
        if form.is_valid():
            saved = form.save()
            saved.calculate_hours()
            messages.success(request, 'Attendance record updated.')
            return redirect('admin_attendance_records')
    else:
        form = AttendanceRecordForm(instance=record)

    return render(request, 'attendance/add_edit_attendance.html', {
        'form':   form,
        'title':  'Edit Attendance Record',
        'is_edit': True,
        'record': record,
    })


@login_required
@user_passes_test(is_admin)
def delete_attendance_record(request, record_id):
    record = get_object_or_404(AttendanceRecord, id=record_id)
    if request.method == 'POST':
        record.delete()
        messages.success(request, 'Attendance record deleted.')
    return redirect('admin_attendance_records')


# ─── DEPARTMENT MANAGEMENT ───────────────────────────────────────────────────

@login_required
@user_passes_test(is_admin)
def manage_departments(request):
    departments = Department.objects.annotate(
        employee_count=Count('employee')
    ).order_by('name')

    if request.method == 'POST':
        form = DepartmentForm(request.POST)
        if form.is_valid():
            dept = form.save()
            messages.success(request, f'Department "{dept.name}" added successfully!')
            return redirect('manage_departments')
    else:
        form = DepartmentForm()

    return render(request, 'attendance/manage_departments.html', {
        'departments': departments,
        'form': form,
    })


@login_required
@user_passes_test(is_admin)
def edit_department(request, dept_id):
    department = get_object_or_404(Department, id=dept_id)

    if request.method == 'POST':
        form = DepartmentForm(request.POST, instance=department)
        if form.is_valid():
            form.save()
            messages.success(request, f'Department "{department.name}" updated!')
            return redirect('manage_departments')
    else:
        form = DepartmentForm(instance=department)

    return render(request, 'attendance/edit_department.html', {
        'form': form,
        'department': department,
        'employee_count': department.employee_set.count(),
    })


@login_required
@user_passes_test(is_admin)
def delete_department(request, dept_id):
    department = get_object_or_404(Department, id=dept_id)
    if request.method == 'POST':
        name = department.name
        department.delete()
        messages.success(request, f'Department "{name}" deleted.')
    return redirect('manage_departments')


# ─── REPORTS ─────────────────────────────────────────────────────────────────

@login_required
@user_passes_test(is_admin)
def reports(request):
    import calendar
    month = int(request.GET.get('month', timezone.now().month))
    year = int(request.GET.get('year', timezone.now().year))
    employees = Employee.objects.filter(is_active=True).select_related('user')

    report_data = []
    for emp in employees:
        records = AttendanceRecord.objects.filter(
            employee=emp, date__month=month, date__year=year
        )
        total_hours = sum([float(r.total_hours or 0) for r in records])
        report_data.append({
            'employee': emp,
            'present': records.filter(status='present').count(),
            'absent': records.filter(status='absent').count(),
            'leave': records.filter(status='leave').count(),
            'total_hours': round(total_hours, 2),
        })

    return render(request, 'attendance/reports.html', {
        'report_data': report_data,
        'month': month,
        'year': year,
        'month_name': calendar.month_name[month],
        'months': [(i, calendar.month_name[i]) for i in range(1, 13)],
        'years': range(2023, timezone.now().year + 1),
    })


# ─── EXCEL EXPORT ────────────────────────────────────────────────────────────

@login_required
@user_passes_test(is_admin)
def export_monthly_report_excel(request):
    import calendar
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.utils import get_column_letter
    from django.http import HttpResponse

    month = int(request.GET.get('month', timezone.now().month))
    year  = int(request.GET.get('year',  timezone.now().year))
    month_name_str = calendar.month_name[month]

    employees = Employee.objects.filter(is_active=True).select_related('user', 'department')

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = f"{month_name_str[:3]} {year}"

    # Title row
    ws.merge_cells('A1:J1')
    ws['A1'] = f"Crefio — Monthly Attendance Report: {month_name_str} {year}"
    ws['A1'].font = Font(bold=True, size=13, color='FFFFFF')
    ws['A1'].fill = PatternFill(start_color='111827', end_color='111827', fill_type='solid')
    ws['A1'].alignment = Alignment(horizontal='center', vertical='center')
    ws.row_dimensions[1].height = 32

    # Header row
    headers = ['Emp ID', 'Full Name', 'Department', 'Designation',
               'Present', 'Absent', 'Leave', 'Half Day', 'Total Hours', 'Attendance %']
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=2, column=col, value=h)
        cell.font = Font(bold=True, color='111827', size=10)
        cell.fill = PatternFill(start_color='BAF2BF', end_color='BAF2BF', fill_type='solid')
        cell.alignment = Alignment(horizontal='center', vertical='center')
    ws.row_dimensions[2].height = 22

    # Data rows
    for row_idx, emp in enumerate(employees, 3):
        records  = AttendanceRecord.objects.filter(employee=emp, date__month=month, date__year=year)
        present  = records.filter(status='present').count()
        absent   = records.filter(status='absent').count()
        leave    = records.filter(status='leave').count()
        half_day = records.filter(status='half_day').count()
        total_hrs = round(sum(float(r.total_hours or 0) for r in records), 2)
        total    = present + absent + leave + half_day
        pct      = f"{round(present / total * 100, 1)}%" if total > 0 else "N/A"

        row_data = [
            emp.employee_id,
            emp.user.get_full_name() or emp.user.username,
            emp.department.name if emp.department else '-',
            emp.designation,
            present, absent, leave, half_day, total_hrs, pct,
        ]
        fill_color = 'FFFFFF' if row_idx % 2 == 0 else 'F7F8FA'
        for col, val in enumerate(row_data, 1):
            cell = ws.cell(row=row_idx, column=col, value=val)
            cell.fill = PatternFill(start_color=fill_color, end_color=fill_color, fill_type='solid')
            cell.alignment = Alignment(horizontal='center' if col > 4 else 'left', vertical='center')

    # Column widths
    for col, width in enumerate([13, 24, 18, 18, 10, 10, 10, 10, 14, 14], 1):
        ws.column_dimensions[get_column_letter(col)].width = width

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = (
        f'attachment; filename="Crefio_Attendance_{month_name_str}_{year}.xlsx"'
    )
    wb.save(response)
    return response


# ─── DETAILED REPORT VIEWS ───────────────────────────────────────────────────

@login_required
@user_passes_test(is_admin)
def employee_monthly_detail(request, emp_id):
    """
    Full month breakdown for one employee:
    every day → check-in time, check-out time, hours, status.
    """
    import calendar

    employee = get_object_or_404(Employee, id=emp_id)
    month = int(request.GET.get('month', timezone.now().month))
    year  = int(request.GET.get('year',  timezone.now().year))

    # All records this employee has for the chosen month
    records_qs = AttendanceRecord.objects.filter(
        employee=employee, date__month=month, date__year=year
    )
    records_map = {r.date: r for r in records_qs}

    # Build a row for every calendar day in the month
    num_days   = calendar.monthrange(year, month)[1]
    today      = timezone.now().date()
    daily_rows = []

    for day in range(1, num_days + 1):
        d      = datetime.date(year, month, day)
        record = records_map.get(d)
        weekday_name = d.strftime('%A')
        is_weekend   = d.weekday() >= 5          # Saturday / Sunday
        is_future    = d > today

        daily_rows.append({
            'date':        d,
            'day_name':    weekday_name,
            'is_weekend':  is_weekend,
            'is_future':   is_future,
            'record':      record,
        })

    present = records_qs.filter(status='present').count()
    absent  = records_qs.filter(status='absent').count()
    leave   = records_qs.filter(status='leave').count()
    half    = records_qs.filter(status='half_day').count()
    total_hours = sum(float(r.total_hours or 0) for r in records_qs)
    avg_checkin  = None
    avg_checkout = None

    checkin_times  = [r.check_in_time  for r in records_qs if r.check_in_time]
    checkout_times = [r.check_out_time for r in records_qs if r.check_out_time]

    if checkin_times:
        avg_sec = sum(t.hour * 3600 + t.minute * 60 + t.second for t in checkin_times) // len(checkin_times)
        avg_checkin = f"{avg_sec // 3600:02d}:{(avg_sec % 3600) // 60:02d}"
    if checkout_times:
        avg_sec = sum(t.hour * 3600 + t.minute * 60 + t.second for t in checkout_times) // len(checkout_times)
        avg_checkout = f"{avg_sec // 3600:02d}:{(avg_sec % 3600) // 60:02d}"

    return render(request, 'attendance/employee_monthly_detail.html', {
        'employee':     employee,
        'daily_rows':   daily_rows,
        'month':        month,
        'year':         year,
        'month_name':   calendar.month_name[month],
        'present':      present,
        'absent':       absent,
        'leave':        leave,
        'half':         half,
        'total_hours':  round(total_hours, 2),
        'avg_checkin':  avg_checkin,
        'avg_checkout': avg_checkout,
        'months': [(i, calendar.month_name[i]) for i in range(1, 13)],
        'years':  range(2023, timezone.now().year + 1),
    })


@login_required
@user_passes_test(is_admin)
def date_wise_report(request):
    """
    Pick any date → see every employee's check-in / check-out for that day.
    Optional filter: ?filter=present | absent | total (default)
    """
    date_str = request.GET.get('date', str(timezone.now().date()))
    try:
        selected_date = datetime.date.fromisoformat(date_str)
    except ValueError:
        selected_date = timezone.now().date()

    status_filter = request.GET.get('filter', 'total')

    all_employees = Employee.objects.filter(is_active=True).select_related('user', 'department')
    records_map   = {
        r.employee_id: r
        for r in AttendanceRecord.objects.filter(date=selected_date).select_related('employee__user')
    }

    all_rows = []
    for emp in all_employees:
        record = records_map.get(emp.id)
        all_rows.append({'employee': emp, 'record': record})

    present_count = sum(1 for r in all_rows if r['record'] and r['record'].check_in_time)
    absent_count  = len(all_rows) - present_count

    # Apply filter
    if status_filter == 'present':
        rows = [r for r in all_rows if r['record'] and r['record'].check_in_time]
    elif status_filter == 'absent':
        rows = [r for r in all_rows if not r['record'] or not r['record'].check_in_time]
    else:
        rows = all_rows

    return render(request, 'attendance/date_wise_report.html', {
        'rows':           rows,
        'selected_date':  selected_date,
        'present_count':  present_count,
        'absent_count':   absent_count,
        'total':          len(all_rows),
        'status_filter':  status_filter,
    })


# ─── LEAVE REQUEST VIEWS ──────────────────────────────────────────────────────

@login_required
def apply_leave(request):
    try:
        employee = request.user.employee
    except Employee.DoesNotExist:
        return redirect('dashboard')

    if request.method == 'POST':
        form = LeaveRequestForm(request.POST)
        if form.is_valid():
            leave = form.save(commit=False)
            leave.employee = employee
            leave.save()
            messages.success(request, 'Leave request submitted! Admin will review it soon.')
            return redirect('my_leaves')
    else:
        form = LeaveRequestForm()

    return render(request, 'attendance/apply_leave.html', {'form': form, 'employee': employee})


@login_required
def my_leaves(request):
    try:
        employee = request.user.employee
    except Employee.DoesNotExist:
        return redirect('dashboard')

    leaves = LeaveRequest.objects.filter(employee=employee)
    return render(request, 'attendance/my_leaves.html', {
        'leaves': leaves,
        'pending': leaves.filter(status='pending').count(),
        'approved': leaves.filter(status='approved').count(),
        'rejected': leaves.filter(status='rejected').count(),
        'employee': employee,
    })


# ─── SUPPORT TICKET VIEWS ────────────────────────────────────────────────────

@login_required
def raise_ticket(request):
    try:
        employee = request.user.employee
    except Employee.DoesNotExist:
        return redirect('dashboard')

    if request.method == 'POST':
        form = SupportTicketForm(request.POST)
        if form.is_valid():
            ticket = form.save(commit=False)
            ticket.employee = employee
            ticket.save()
            messages.success(request, f'Ticket #{ticket.id} raised successfully! Admin will respond soon.')
            return redirect('my_tickets')
    else:
        form = SupportTicketForm()

    return render(request, 'attendance/raise_ticket.html', {'form': form, 'employee': employee})


@login_required
def my_tickets(request):
    try:
        employee = request.user.employee
    except Employee.DoesNotExist:
        return redirect('dashboard')

    tickets = SupportTicket.objects.filter(employee=employee)
    return render(request, 'attendance/my_tickets.html', {
        'tickets': tickets,
        'open_count': tickets.filter(status='open').count(),
        'resolved_count': tickets.filter(status='resolved').count(),
        'employee': employee,
    })


# ─── ATTENDANCE CORRECTION REQUESTS (Employee) ───────────────────────────────

@login_required
def request_correction(request):
    try:
        employee = request.user.employee
    except Employee.DoesNotExist:
        return redirect('dashboard')

    if request.method == 'POST':
        form = AttendanceCorrectionForm(request.POST)
        if form.is_valid():
            correction = form.save(commit=False)
            correction.employee = employee
            correction.save()
            messages.success(request, 'Correction request submitted! Admin will review it soon.')
            return redirect('my_corrections')
    else:
        form = AttendanceCorrectionForm(initial={'date': timezone.now().date()})

    recent = AttendanceCorrectionRequest.objects.filter(employee=employee)[:5]
    return render(request, 'attendance/request_correction.html', {
        'form': form,
        'employee': employee,
        'recent': recent,
    })


@login_required
def my_corrections(request):
    try:
        employee = request.user.employee
    except Employee.DoesNotExist:
        return redirect('dashboard')

    corrections = AttendanceCorrectionRequest.objects.filter(employee=employee)
    return render(request, 'attendance/my_corrections.html', {
        'corrections': corrections,
        'pending_count':  corrections.filter(status='pending').count(),
        'approved_count': corrections.filter(status='approved').count(),
        'rejected_count': corrections.filter(status='rejected').count(),
        'employee': employee,
    })


# ─── ADMIN LEAVE & TICKET VIEWS ──────────────────────────────────────────────

@login_required
@user_passes_test(is_admin)
def admin_leaves(request):
    status_filter = request.GET.get('status', '')
    leaves = LeaveRequest.objects.select_related('employee__user', 'employee__department').all()
    if status_filter:
        leaves = leaves.filter(status=status_filter)

    return render(request, 'attendance/admin_leaves.html', {
        'leaves': leaves,
        'status_filter': status_filter,
        'pending_count': LeaveRequest.objects.filter(status='pending').count(),
    })


@login_required
@user_passes_test(is_admin)
def admin_leave_action(request, leave_id):
    leave = get_object_or_404(LeaveRequest, id=leave_id)
    if request.method == 'POST':
        form = AdminLeaveResponseForm(request.POST, instance=leave)
        if form.is_valid():
            form.save()
            messages.success(request, f'Leave request {leave.get_status_display()} successfully.')
            return redirect('admin_leaves')
    else:
        form = AdminLeaveResponseForm(instance=leave)

    return render(request, 'attendance/admin_leave_action.html', {'form': form, 'leave': leave})


@login_required
@user_passes_test(is_admin)
def admin_tickets(request):
    status_filter = request.GET.get('status', '')
    tickets = SupportTicket.objects.select_related('employee__user', 'employee__department').all()
    if status_filter:
        tickets = tickets.filter(status=status_filter)

    return render(request, 'attendance/admin_tickets.html', {
        'tickets': tickets,
        'status_filter': status_filter,
        'open_count': SupportTicket.objects.filter(status='open').count(),
    })


@login_required
@user_passes_test(is_admin)
def admin_ticket_action(request, ticket_id):
    ticket = get_object_or_404(SupportTicket, id=ticket_id)
    if request.method == 'POST':
        form = AdminTicketResponseForm(request.POST, instance=ticket)
        if form.is_valid():
            form.save()
            messages.success(request, f'Ticket #{ticket.id} updated successfully.')
            return redirect('admin_tickets')
    else:
        form = AdminTicketResponseForm(instance=ticket)

    return render(request, 'attendance/admin_ticket_action.html', {'form': form, 'ticket': ticket})


# ─── ADMIN CORRECTION VIEWS ──────────────────────────────────────────────────

@login_required
@user_passes_test(is_admin)
def admin_corrections(request):
    status_filter = request.GET.get('status', 'pending')
    corrections = AttendanceCorrectionRequest.objects.select_related(
        'employee__user'
    ).all()
    if status_filter:
        corrections = corrections.filter(status=status_filter)

    return render(request, 'attendance/admin_corrections.html', {
        'corrections':    corrections,
        'status_filter':  status_filter,
        'pending_count':  AttendanceCorrectionRequest.objects.filter(status='pending').count(),
    })


@login_required
@user_passes_test(is_admin)
def admin_correction_action(request, correction_id):
    correction = get_object_or_404(AttendanceCorrectionRequest, id=correction_id)

    if request.method == 'POST':
        form = AdminCorrectionResponseForm(request.POST, instance=correction)
        if form.is_valid():
            saved = form.save()

            if saved.status == 'approved':
                record, _ = AttendanceRecord.objects.get_or_create(
                    employee=saved.employee,
                    date=saved.date,
                    defaults={'status': 'present'}
                )
                if saved.requested_check_in:
                    record.check_in_time = saved.requested_check_in
                    record.status = 'present'
                if saved.requested_check_out:
                    record.check_out_time = saved.requested_check_out
                record.save()
                record.calculate_hours()
                messages.success(
                    request,
                    f'Approved — attendance for {saved.employee.user.get_full_name()} '
                    f'on {saved.date} has been updated.'
                )
            else:
                messages.info(
                    request,
                    f'Correction request for {saved.employee.user.get_full_name()} rejected.'
                )
            return redirect('admin_corrections')
    else:
        form = AdminCorrectionResponseForm(instance=correction)

    return render(request, 'attendance/admin_correction_action.html', {
        'form':       form,
        'correction': correction,
    })


# ─── SALARY VIEWS ────────────────────────────────────────────────────────────

@login_required
@user_passes_test(is_admin)
def admin_salary(request):
    """Admin sees all employees' salary for a selected month/year."""
    import calendar
    month = int(request.GET.get('month', timezone.now().month))
    year  = int(request.GET.get('year',  timezone.now().year))
    status_filter = request.GET.get('filter', 'total')

    employees  = Employee.objects.filter(is_active=True).select_related('user', 'department')
    salary_map = {
        s.employee_id: s
        for s in SalaryRecord.objects.filter(month=month, year=year)
    }

    all_rows = []
    for emp in employees:
        all_rows.append({
            'employee': emp,
            'salary':   salary_map.get(emp.id),
        })

    paid_count   = sum(1 for r in all_rows if r['salary'] and r['salary'].is_paid)
    unpaid_count = len(all_rows) - paid_count

    if status_filter == 'paid':
        rows = [r for r in all_rows if r['salary'] and r['salary'].is_paid]
    elif status_filter == 'pending':
        rows = [r for r in all_rows if not r['salary'] or not r['salary'].is_paid]
    else:
        rows = all_rows

    return render(request, 'attendance/admin_salary.html', {
        'rows':          rows,
        'month':         month,
        'year':          year,
        'month_name':    calendar.month_name[month],
        'paid_count':    paid_count,
        'unpaid_count':  unpaid_count,
        'total':         len(all_rows),
        'status_filter': status_filter,
        'months': [(i, calendar.month_name[i]) for i in range(1, 13)],
        'years':  range(2023, timezone.now().year + 1),
    })


@login_required
@user_passes_test(is_admin)
def update_salary(request, emp_id):
    import calendar
    employee = get_object_or_404(Employee, id=emp_id)
    month = int(request.GET.get('month', timezone.now().month))
    year  = int(request.GET.get('year',  timezone.now().year))

    with transaction.atomic():
        salary, _ = SalaryRecord.objects.get_or_create(
            employee=employee, month=month, year=year,
            defaults={'basic_salary': 0, 'allowances': 0, 'absent_days': 0}
        )

    # Auto-calculate absent+leave days from attendance (exclude Sundays)
    absent_records = AttendanceRecord.objects.filter(
        employee=employee, date__month=month, date__year=year,
        status__in=['absent', 'leave']
    )
    absent_days = sum(1 for r in absent_records if r.date.weekday() != 6)
    salary.absent_days = absent_days
    salary.save()

    daily_rate = round(float(salary.basic_salary) / 30.4, 2) if salary.basic_salary else 0

    if request.method == 'POST':
        form = SalaryForm(request.POST, instance=salary)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.absent_days = absent_days
            obj.save()
            messages.success(
                request,
                f'Salary for {employee.user.get_full_name()} '
                f'({calendar.month_name[month]} {year}) saved successfully!'
            )
            return redirect(f"{request.path_info}?month={month}&year={year}&saved=1")
    else:
        form = SalaryForm(instance=salary)

    return render(request, 'attendance/update_salary.html', {
        'form':        form,
        'employee':    employee,
        'salary':      salary,
        'month':       month,
        'year':        year,
        'month_name':  calendar.month_name[month],
        'absent_days': absent_days,
        'daily_rate':  daily_rate,
        'months': [(i, calendar.month_name[i]) for i in range(1, 13)],
        'years':  range(2023, timezone.now().year + 1),
        'saved':  request.GET.get('saved'),
    })


@login_required
def my_salary(request):
    """Employee sees their own salary slips."""
    import calendar
    try:
        employee = request.user.employee
    except Employee.DoesNotExist:
        return redirect('dashboard')

    salaries = SalaryRecord.objects.filter(employee=employee)

    # Current month salary highlighted
    current_month = timezone.now().month
    current_year  = timezone.now().year
    current_salary = salaries.filter(month=current_month, year=current_year).first()

    return render(request, 'attendance/my_salary.html', {
        'employee':       employee,
        'salaries':       salaries,
        'current_salary': current_salary,
        'current_month':  calendar.month_name[current_month],
        'current_year':   current_year,
    })


@login_required
def salary_slip(request, salary_id):
    import calendar
    slip = get_object_or_404(SalaryRecord, id=salary_id)
    # Access control: admin can view any, employee only their own
    if not request.user.is_staff:
        try:
            if slip.employee != request.user.employee:
                messages.error(request, 'Access denied.')
                return redirect('my_salary')
        except Employee.DoesNotExist:
            return redirect('my_salary')
    daily_rate = round(float(slip.basic_salary) / 30.4, 2) if slip.basic_salary else 0
    total_earnings = float(slip.basic_salary) + float(slip.allowances)
    return render(request, 'attendance/salary_slip.html', {
        'slip':           slip,
        'employee':       slip.employee,
        'month_name':     calendar.month_name[slip.month],
        'daily_rate':     daily_rate,
        'total_earnings': round(total_earnings, 2),
    })
