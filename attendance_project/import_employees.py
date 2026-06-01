#!/usr/bin/env python
"""
Bulk-import employees from an Excel sheet straight into the database,
plus create the two super-admin logins (Parikshit & Nishil).

Idempotent: re-running updates existing users (matched by username) instead
of creating duplicates, so it's safe to run again after fixing the sheet.

Usage (locally OR on the server — identical):

    cd /var/www/hrms/attendance_project            # the dir with manage.py
    set -a; source /var/www/hrms/.env; set +a      # load DATABASE_URL etc.
    python import_employees.py "Employee list with emails.xlsx"

If no path is given it looks for "Employee list with emails.xlsx" next to this script.
Override the super-admin passwords with env vars PARIKSHIT_PASSWORD / NISHIL_PASSWORD.
"""
import os
import re
import sys
from pathlib import Path

# ─── Django bootstrap ────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "attendance_project.settings")

import django

django.setup()

from django.contrib.auth.models import User
from django.db import transaction
from attendance.models import Employee, Department
import openpyxl

# ─── Super-admin accounts ────────────────────────────────────────────────────
# Change these passwords, or set PARIKSHIT_PASSWORD / NISHIL_PASSWORD env vars.
SUPER_ADMINS = [
    {
        "username": "parikshit",
        "email": "parikshit@crefio.in",
        "first_name": "Parikshit",
        "last_name": "Pandey",
        "department": "Tech",
        "designation": "Super Admin",
        "password": os.environ.get("PARIKSHIT_PASSWORD", "Crefio@2025"),
    },
    {
        "username": "nishil",
        "email": "nishil@crefio.in",
        "first_name": "Nishil",
        "last_name": "",
        "department": "Product",  # also oversees Marketing; approvals are global
        "designation": "Super Admin",
        "password": os.environ.get("NISHIL_PASSWORD", "Crefio@2025"),
    },
]


def next_emp_id_counter():
    """Return a callable that hands out CRF001, CRF002, ... starting after the highest existing id."""
    nums = []
    for eid in Employee.objects.values_list("employee_id", flat=True):
        m = re.search(r"(\d+)$", eid or "")
        if m:
            nums.append(int(m.group(1)))
    state = {"n": max(nums) if nums else 0}

    def _next():
        state["n"] += 1
        return f"CRF{state['n']:03d}"

    return _next


def clean_phone(value):
    if value is None:
        return ""
    if isinstance(value, float):  # Excel stores numbers as floats
        return str(int(value))
    return str(value).strip()


def upsert_employee(*, username, email, first_name, last_name, dept_name, designation, password, is_super, gen_id):
    """Create or update one User + linked Employee. Returns (action, employee)."""
    department = None
    if dept_name:
        department, _ = Department.objects.get_or_create(name=dept_name)

    with transaction.atomic():
        user, created = User.objects.get_or_create(
            username=username,
            defaults={"email": email, "first_name": first_name, "last_name": last_name},
        )
        user.email = email
        user.first_name = first_name
        user.last_name = last_name
        user.is_staff = is_super
        user.is_superuser = is_super
        if password:
            user.set_password(password)
        user.save()

        emp, emp_created = Employee.objects.get_or_create(
            user=user,
            defaults={"employee_id": gen_id(), "designation": designation},
        )
        emp.department = department
        emp.designation = designation or emp.designation
        if not emp.employee_id:
            emp.employee_id = gen_id()
        emp.save()

    return ("created" if created else "updated"), emp


def main():
    if len(sys.argv) > 1:
        xlsx_path = Path(sys.argv[1]).expanduser()
    else:
        xlsx_path = BASE_DIR / "Employee list with emails.xlsx"

    if not xlsx_path.exists():
        sys.exit(f"❌ Excel file not found: {xlsx_path}")

    gen_id = next_emp_id_counter()
    results = []

    # ── Employees from the spreadsheet ──
    wb = openpyxl.load_workbook(xlsx_path, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    header = [str(c).strip().lower() if c else "" for c in rows[0]]

    def col(row, name):
        try:
            return row[header.index(name)]
        except (ValueError, IndexError):
            return None

    for row in rows[1:]:
        if not row or not any(row):
            continue
        email = (col(row, "email") or "").strip()
        username = (col(row, "username") or "").strip() or email.split("@")[0]
        if not username:
            continue
        action, emp = upsert_employee(
            username=username,
            email=email,
            first_name=(col(row, "first name") or "").strip(),
            last_name=(col(row, "last name") or "").strip(),
            dept_name=(col(row, "department") or "").strip(),
            designation=(col(row, "designation") or "").strip(),
            password=(col(row, "password") or "").strip(),
            is_super=False,
            gen_id=gen_id,
        )
        # phone lives only on Employee
        phone = clean_phone(col(row, "phone"))
        if phone:
            emp.phone = phone
            emp.save(update_fields=["phone"])
        results.append((action, emp.employee_id, username, emp.department, "employee"))

    # ── Super admins ──
    for sa in SUPER_ADMINS:
        action, emp = upsert_employee(
            username=sa["username"],
            email=sa["email"],
            first_name=sa["first_name"],
            last_name=sa["last_name"],
            dept_name=sa["department"],
            designation=sa["designation"],
            password=sa["password"],
            is_super=True,
            gen_id=gen_id,
        )
        results.append((action, emp.employee_id, sa["username"], emp.department, "SUPERADMIN"))

    # ── Summary ──
    print("\n  ACTION    EMP_ID   USERNAME              DEPARTMENT      ROLE")
    print("  " + "-" * 70)
    for action, eid, uname, dept, role in results:
        print(f"  {action:<8}  {eid:<7}  {uname:<20}  {str(dept):<14}  {role}")
    print(
        f"\n✅ Done. {len(results)} accounts processed "
        f"({sum(1 for r in results if r[0]=='created')} created, "
        f"{sum(1 for r in results if r[0]=='updated')} updated)."
    )
    print("Super admins (is_staff + is_superuser) can approve across ALL teams.")


if __name__ == "__main__":
    main()
