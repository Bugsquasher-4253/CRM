from django.urls import path
from . import views

urlpatterns = [
    # Auth
    path('', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('switch-panel/', views.switch_panel, name='switch_panel'),

    # Employee pages
    path('dashboard/', views.dashboard, name='dashboard'),
    path('dismiss-doc-reminder/', views.dismiss_document_reminder, name='dismiss_document_reminder'),
    path('checkin/', views.check_in, name='check_in'),
    path('checkout/', views.check_out, name='check_out'),
    path('my-attendance/', views.my_attendance, name='my_attendance'),
    path('profile/edit/', views.edit_profile, name='edit_profile'),

    # Leave requests (employee)
    path('leave/apply/', views.apply_leave, name='apply_leave'),
    path('leave/my-leaves/', views.my_leaves, name='my_leaves'),

    # Support tickets (employee)
    path('tickets/raise/', views.raise_ticket, name='raise_ticket'),
    path('tickets/my-tickets/', views.my_tickets, name='my_tickets'),
    path('tickets/<int:ticket_id>/edit/', views.edit_ticket, name='edit_ticket'),

    # Attendance correction (employee)
    path('attendance/correction/', views.request_correction, name='request_correction'),
    path('attendance/correction/my-requests/', views.my_corrections, name='my_corrections'),

    # Admin pages
    path('admin-panel/', views.admin_dashboard, name='admin_dashboard'),
    path('employees/', views.manage_employees, name='manage_employees'),
    path('employees/add/', views.add_employee, name='add_employee'),
    path('employees/<int:emp_id>/', views.view_employee_detail, name='employee_detail'),
    path('employees/<int:emp_id>/edit/', views.edit_employee_admin, name='edit_employee_admin'),
    path('employees/<int:emp_id>/toggle-active/', views.toggle_employee_active, name='toggle_employee_active'),
    path('employees/<int:emp_id>/toggle-admin/', views.toggle_employee_admin, name='toggle_employee_admin'),
    path('employees/<int:emp_id>/reset-password/', views.reset_employee_password, name='reset_employee_password'),
    path('admin-panel/attendance/', views.admin_attendance_records, name='admin_attendance_records'),
    path('admin-panel/attendance/add/', views.add_attendance_record, name='add_attendance_record'),
    path('admin-panel/attendance/<int:record_id>/edit/', views.edit_attendance_record, name='edit_attendance_record'),
    path('admin-panel/attendance/<int:record_id>/delete/', views.delete_attendance_record, name='delete_attendance_record'),
    path('admin-panel/departments/', views.manage_departments, name='manage_departments'),
    path('admin-panel/departments/<int:dept_id>/edit/', views.edit_department, name='edit_department'),
    path('admin-panel/departments/<int:dept_id>/delete/', views.delete_department, name='delete_department'),
    path('reports/', views.reports, name='reports'),
    path('reports/export/excel/', views.export_monthly_report_excel, name='export_monthly_report_excel'),
    path('reports/employee/<int:emp_id>/', views.employee_monthly_detail, name='employee_monthly_detail'),
    path('reports/date/', views.date_wise_report, name='date_wise_report'),

    # Admin leave management
    path('admin-panel/leaves/', views.admin_leaves, name='admin_leaves'),
    path('admin-panel/leaves/<int:leave_id>/', views.admin_leave_action, name='admin_leave_action'),

    # Admin correction management
    path('admin-panel/corrections/', views.admin_corrections, name='admin_corrections'),
    path('admin-panel/corrections/<int:correction_id>/', views.admin_correction_action, name='admin_correction_action'),

    # Admin ticket management
    path('admin-panel/tickets/', views.admin_tickets, name='admin_tickets'),
    path('admin-panel/tickets/<int:ticket_id>/', views.admin_ticket_action, name='admin_ticket_action'),

    # One-click email actions (approve/reject via signed token — no login needed)
    path('ea/<str:token>/', views.email_action, name='email_action'),

    # Salary
    path('admin-panel/salary/', views.admin_salary, name='admin_salary'),
    path('admin-panel/salary/<int:emp_id>/', views.update_salary, name='update_salary'),
    path('salary/', views.my_salary, name='my_salary'),
    path('salary/slip/<int:salary_id>/', views.salary_slip, name='salary_slip'),
]
