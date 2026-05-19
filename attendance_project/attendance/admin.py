from django.contrib import admin
from .models import Department, Employee, AttendanceRecord


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ['name', 'created_at']
    search_fields = ['name']


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ['employee_id', 'get_full_name', 'designation', 'department', 'is_active']
    list_filter = ['department', 'is_active']
    search_fields = ['employee_id', 'user__first_name', 'user__last_name']

    def get_full_name(self, obj):
        return obj.user.get_full_name()
    get_full_name.short_description = 'Name'


@admin.register(AttendanceRecord)
class AttendanceRecordAdmin(admin.ModelAdmin):
    list_display = ['employee', 'date', 'check_in_time', 'check_out_time', 'status', 'total_hours']
    list_filter = ['status', 'date']
    search_fields = ['employee__user__first_name', 'employee__employee_id']
    date_hierarchy = 'date'
