from django import forms
from django.contrib.auth.models import User
from .models import Employee, LeaveRequest, SupportTicket, SalaryRecord, Department, AttendanceRecord, AttendanceCorrectionRequest


class LoginForm(forms.Form):
    email = forms.EmailField(widget=forms.EmailInput(attrs={
        'class': 'form-control form-control-lg',
        'placeholder': 'Enter your email address',
        'autocomplete': 'email',
    }))
    password = forms.CharField(widget=forms.PasswordInput(attrs={
        'class': 'form-control form-control-lg',
        'placeholder': 'Enter your password',
    }))


class UserForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}))

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'password']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
        }


class EmployeeForm(forms.ModelForm):
    class Meta:
        model = Employee
        fields = ['department', 'phone', 'designation', 'date_joined', 'profile_photo']
        widgets = {
            'department': forms.Select(attrs={'class': 'form-select'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'designation': forms.TextInput(attrs={'class': 'form-control'}),
            'date_joined': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }


class LeaveRequestForm(forms.ModelForm):
    class Meta:
        model = LeaveRequest
        fields = ['leave_type', 'from_date', 'to_date', 'reason']
        widgets = {
            'leave_type': forms.Select(attrs={'class': 'form-select form-select-lg'}),
            'from_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'to_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'reason': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Please explain the reason for your leave request...',
            }),
        }

    def clean(self):
        cleaned_data = super().clean()
        from_date = cleaned_data.get('from_date')
        to_date = cleaned_data.get('to_date')
        if from_date and to_date and to_date < from_date:
            raise forms.ValidationError('End date cannot be before start date.')
        return cleaned_data


class SupportTicketForm(forms.ModelForm):
    class Meta:
        model = SupportTicket
        fields = ['subject', 'priority', 'description']
        widgets = {
            'subject': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Brief summary of your issue...',
            }),
            'priority': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 5,
                'placeholder': 'Describe your issue in detail...',
            }),
        }


class EmployeeProfileEditForm(forms.Form):
    """Employee can edit their own basic info + upload documents."""
    first_name = forms.CharField(max_length=50, widget=forms.TextInput(attrs={
        'class': 'form-control', 'placeholder': 'First name',
    }))
    last_name = forms.CharField(max_length=50, widget=forms.TextInput(attrs={
        'class': 'form-control', 'placeholder': 'Last name',
    }))
    email = forms.EmailField(widget=forms.EmailInput(attrs={
        'class': 'form-control', 'placeholder': 'Email address',
    }))
    phone = forms.CharField(max_length=15, required=False, widget=forms.TextInput(attrs={
        'class': 'form-control', 'placeholder': 'Phone number',
    }))
    profile_photo = forms.ImageField(required=False, widget=forms.FileInput(attrs={
        'class': 'form-control', 'accept': 'image/*',
    }))
    aadhaar_card = forms.FileField(required=False, widget=forms.FileInput(attrs={
        'class': 'form-control', 'accept': '.pdf,.jpg,.jpeg,.png',
    }))
    pan_card = forms.FileField(required=False, widget=forms.FileInput(attrs={
        'class': 'form-control', 'accept': '.pdf,.jpg,.jpeg,.png',
    }))


class AdminLeaveResponseForm(forms.ModelForm):
    class Meta:
        model = LeaveRequest
        fields = ['status', 'admin_note']
        widgets = {
            'status': forms.Select(attrs={'class': 'form-select'}),
            'admin_note': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Add a note for the employee (optional)...',
            }),
        }


class AdminTicketResponseForm(forms.ModelForm):
    class Meta:
        model = SupportTicket
        fields = ['status', 'admin_response']
        widgets = {
            'status': forms.Select(attrs={'class': 'form-select'}),
            'admin_response': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Write your response to the employee...',
            }),
        }


class AdminEmployeeEditForm(forms.Form):
    first_name = forms.CharField(max_length=50, widget=forms.TextInput(attrs={'class': 'form-control'}))
    last_name = forms.CharField(max_length=50, widget=forms.TextInput(attrs={'class': 'form-control'}))
    email = forms.EmailField(widget=forms.EmailInput(attrs={'class': 'form-control'}))
    username = forms.CharField(max_length=150, widget=forms.TextInput(attrs={'class': 'form-control'}))
    is_active_user = forms.BooleanField(required=False, widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}))
    employee_id = forms.CharField(max_length=20, widget=forms.TextInput(attrs={'class': 'form-control'}))
    department = forms.ModelChoiceField(
        queryset=Department.objects.all(), required=False,
        empty_label='— No Department —',
        widget=forms.Select(attrs={'class': 'form-select'}))
    designation = forms.CharField(max_length=100, widget=forms.TextInput(attrs={'class': 'form-control'}))
    phone = forms.CharField(max_length=15, required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    date_joined = forms.DateField(widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}))
    profile_photo = forms.ImageField(required=False, widget=forms.FileInput(attrs={
        'class': 'form-control', 'accept': 'image/*'}))
    aadhaar_card = forms.FileField(required=False, widget=forms.FileInput(attrs={
        'class': 'form-control', 'accept': '.pdf,.jpg,.jpeg,.png'}))
    pan_card = forms.FileField(required=False, widget=forms.FileInput(attrs={
        'class': 'form-control', 'accept': '.pdf,.jpg,.jpeg,.png'}))


class AttendanceRecordForm(forms.ModelForm):
    class Meta:
        model = AttendanceRecord
        fields = ['employee', 'date', 'check_in_time', 'check_out_time', 'status', 'notes']
        widgets = {
            'employee': forms.Select(attrs={'class': 'form-select'}),
            'date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'check_in_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'check_out_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2,
                                           'placeholder': 'Optional note...'}),
        }


class AdminPasswordChangeForm(forms.Form):
    new_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'New password'}))
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Confirm new password'}))

    def clean(self):
        cleaned_data = super().clean()
        p1 = cleaned_data.get('new_password')
        p2 = cleaned_data.get('confirm_password')
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError('Passwords do not match.')
        return cleaned_data


class AttendanceCorrectionForm(forms.ModelForm):
    class Meta:
        model = AttendanceCorrectionRequest
        fields = ['date', 'requested_check_in', 'requested_check_out', 'reason']
        widgets = {
            'date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'requested_check_in': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'requested_check_out': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'reason': forms.Textarea(attrs={
                'class': 'form-control', 'rows': 3,
                'placeholder': 'Explain what happened (e.g. forgot to check in, system was down...)',
            }),
        }

    def clean(self):
        cleaned_data = super().clean()
        ci = cleaned_data.get('requested_check_in')
        co = cleaned_data.get('requested_check_out')
        if not ci and not co:
            raise forms.ValidationError('Please provide at least one time (check-in or check-out).')
        if ci and co and co <= ci:
            raise forms.ValidationError('Check-out time must be after check-in time.')
        return cleaned_data


class AdminCorrectionResponseForm(forms.ModelForm):
    class Meta:
        model = AttendanceCorrectionRequest
        fields = ['status', 'admin_note']
        widgets = {
            'status': forms.Select(attrs={'class': 'form-select'}),
            'admin_note': forms.Textarea(attrs={
                'class': 'form-control', 'rows': 2,
                'placeholder': 'Optional note for the employee...',
            }),
        }


class DepartmentForm(forms.ModelForm):
    class Meta:
        model = Department
        fields = ['name', 'description']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control', 'placeholder': 'e.g. Engineering, HR, Sales...',
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control', 'rows': 2,
                'placeholder': 'Short description (optional)',
            }),
        }


class SalaryForm(forms.ModelForm):
    class Meta:
        model = SalaryRecord
        fields = ['basic_salary', 'allowances', 'is_paid', 'paid_date', 'notes']
        widgets = {
            'basic_salary': forms.NumberInput(attrs={
                'class': 'form-control', 'placeholder': 'e.g. 25000', 'step': '0.01',
            }),
            'allowances': forms.NumberInput(attrs={
                'class': 'form-control', 'placeholder': 'e.g. 5000', 'step': '0.01',
            }),
            'is_paid': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'paid_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'notes': forms.Textarea(attrs={
                'class': 'form-control', 'rows': 2,
                'placeholder': 'Any note (e.g. Bonus included)',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for fname in ('basic_salary', 'allowances'):
            if float(self.initial.get(fname) or 0) == 0:
                self.initial[fname] = ''
