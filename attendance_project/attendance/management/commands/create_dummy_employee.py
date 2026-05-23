"""
Management command: create_dummy_employee
Creates a test employee with a full May 2026 attendance record to verify
salary calculations:
  - 10 leave days  (May 5–15, skipping Sunday May 11)
  - 2  half days   (May 16–17, 2 hrs work → status half_day)
  - 15 present days (remaining Mon–Sat)
  - Basic salary ₹30,000 | Allowances ₹5,000

Expected deductions:
  daily_rate   = 30000 / 30.4 = ₹986.84
  leave        = 10 × 986.84  = ₹9,868.42
  half days    = 2  × 493.42  = ₹986.84
  total deduct = ₹10,855.26
  net salary   = 30000 + 5000 − 10855.26 = ₹24,144.74
"""

import datetime
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from attendance.models import Employee, AttendanceRecord, SalaryRecord, Department


class Command(BaseCommand):
    help = 'Create a dummy employee with May 2026 attendance for salary testing'

    def handle(self, *args, **options):
        # ── 1. Get or create a department ────────────────────────────────────
        dept, _ = Department.objects.get_or_create(name='Testing')

        # ── 2. Create Django user ─────────────────────────────────────────────
        username = 'dummy_test_emp'
        if User.objects.filter(username=username).exists():
            self.stdout.write(self.style.WARNING(
                f'User "{username}" already exists — deleting and recreating.'
            ))
            User.objects.filter(username=username).delete()

        user = User.objects.create_user(
            username=username,
            password='Test@1234',
            first_name='Dummy',
            last_name='Employee',
            email='dummy.test@crefio.in',
        )

        # ── 3. Create Employee profile ────────────────────────────────────────
        emp = Employee.objects.create(
            user=user,
            employee_id='CRF-TEST',
            department=dept,
            designation='Test Engineer',
            date_joined=datetime.date(2026, 1, 1),
            is_active=True,
        )
        self.stdout.write(self.style.SUCCESS(
            f'Created employee: {emp.user.get_full_name()} (ID: {emp.employee_id})'
        ))

        # ── 4. Build May 2026 attendance ──────────────────────────────────────
        MONTH, YEAR = 5, 2026

        # Leave days: May 5–15 excluding Sunday May 11  → 10 days
        leave_dates = [
            datetime.date(2026, 5, day)
            for day in range(5, 16)
            if datetime.date(2026, 5, day).weekday() != 6   # skip Sunday
        ]
        assert len(leave_dates) == 10, f'Expected 10 leave days, got {len(leave_dates)}'

        # Half-day dates: May 19 (Mon) and May 20 (Tue) — both verified non-Sunday
        half_day_dates = [datetime.date(2026, 5, 19), datetime.date(2026, 5, 20)]

        # All working days in May (Mon–Sat)
        all_working = [
            datetime.date(2026, 5, d)
            for d in range(1, 32)
            if datetime.date(2026, 5, d).weekday() != 6
        ]

        special = set(leave_dates + half_day_dates)
        present_dates = [d for d in all_working if d not in special]

        AttendanceRecord.objects.filter(employee=emp, date__month=MONTH, date__year=YEAR).delete()

        # Present records: 09:00 → 18:00  (9 hrs → status=present)
        for d in present_dates:
            r = AttendanceRecord(
                employee=emp,
                date=d,
                check_in_time=datetime.time(9, 0),
                check_out_time=datetime.time(18, 0),
                status='present',
            )
            r.save()
            r.calculate_hours()   # sets total_hours and confirms status

        # Half-day records: 09:00 → 11:00  (2 hrs → status=half_day)
        for d in half_day_dates:
            r = AttendanceRecord(
                employee=emp,
                date=d,
                check_in_time=datetime.time(9, 0),
                check_out_time=datetime.time(11, 0),
                status='half_day',
            )
            r.save()
            r.calculate_hours()

        # Leave records
        for d in leave_dates:
            AttendanceRecord.objects.create(
                employee=emp,
                date=d,
                check_in_time=None,
                check_out_time=None,
                status='leave',
            )

        self.stdout.write(self.style.SUCCESS(
            f'Created {len(present_dates)} present + {len(half_day_dates)} half-day + {len(leave_dates)} leave records'
        ))

        # ── 5. Create Salary record ───────────────────────────────────────────
        BASIC   = 30000
        ALLOWANCES = 5000

        salary, _ = SalaryRecord.objects.get_or_create(
            employee=emp, month=MONTH, year=YEAR,
            defaults={'basic_salary': BASIC, 'allowances': ALLOWANCES}
        )
        salary.basic_salary = BASIC
        salary.allowances   = ALLOWANCES
        salary.absent_days  = len(leave_dates)   # 10
        salary.half_days    = len(half_day_dates) # 2
        salary.save()  # auto-calculates deductions & net_salary

        # ── 6. Print verification summary ────────────────────────────────────
        daily = round(BASIC / 30.4, 2)
        self.stdout.write('\n' + '='*52)
        self.stdout.write(self.style.SUCCESS('  SALARY VERIFICATION SUMMARY'))
        self.stdout.write('='*52)
        self.stdout.write(f'  Basic salary   : ₹{BASIC:,.2f}')
        self.stdout.write(f'  Allowances     : ₹{ALLOWANCES:,.2f}')
        self.stdout.write(f'  Daily rate     : ₹{daily:,.2f}  (30000 ÷ 30.4)')
        self.stdout.write(f'  Leave days     : {len(leave_dates)}  × ₹{daily:,.2f} = ₹{len(leave_dates)*daily:,.2f}')
        self.stdout.write(f'  Half days      : {len(half_day_dates)}  × ₹{daily/2:,.2f} = ₹{len(half_day_dates)*(daily/2):,.2f}')
        self.stdout.write(f'  Total deduction: ₹{float(salary.deductions):,.2f}')
        self.stdout.write(f'  Net salary     : ₹{float(salary.net_salary):,.2f}')
        self.stdout.write('='*52)
        self.stdout.write(f'  Login → username: {username}  password: Test@1234')
        self.stdout.write('='*52 + '\n')
