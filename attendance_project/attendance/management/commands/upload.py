import pandas as pd
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from attendance.models import Department, Employee
from django.utils.crypto import get_random_string


class Command(BaseCommand):
    help = "Upload Employees from Excel"

    def add_arguments(self, parser):
        parser.add_argument("excel_file", type=str)

    def handle(self, *args, **kwargs):

        excel_file = kwargs["excel_file"]

        try:
            df = pd.read_excel(excel_file)

            for index, row in df.iterrows():

                first_name = str(row["first_name"]).strip()
                last_name = str(row["last_name"]).strip()
                username = str(row["username"]).strip()
                email = str(row["email"]).strip()
                employee_id = str(row["employee_id"]).strip()
                department_name = str(row["department"]).strip()
                phone = str(row["phone"]).strip()
                designation = str(row["designation"]).strip()

                # Create Department
                department, created = Department.objects.get_or_create(name=department_name)

                # Skip duplicate usernames
                if User.objects.filter(username=username).exists():
                    self.stdout.write(self.style.WARNING(f"Username {username} already exists"))
                    continue

                # Generate Password
                password = get_random_string(8)

                # Create User
                user = User.objects.create_user(
                    username=username, email=email, password=password, first_name=first_name, last_name=last_name
                )

                # Create Employee
                employee = Employee.objects.create(
                    user=user, employee_id=employee_id, department=department, phone=phone, designation=designation
                )

                self.stdout.write(self.style.SUCCESS(f"Employee Created: {employee.employee_id}"))

            self.stdout.write(self.style.SUCCESS("Excel Uploaded Successfully"))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error: {str(e)}"))
