"""
Management command: backfill_joined_dates

Run: python manage.py backfill_joined_dates

Fixes any CustomUser with a null joined_date by reading
Django's built-in date_joined field (which is always populated).
Also assigns employee IDs to any user missing one.
"""
from django.core.management.base import BaseCommand
from core.models import CustomUser, Organization


class Command(BaseCommand):
    help = 'Backfill joined_date and employee_id for existing users'

    def handle(self, *args, **options):
        fixed_dates = 0
        fixed_ids = 0

        for org in Organization.objects.all():
            prefix_raw = ''.join(c for c in org.name.upper() if c.isalpha())
            prefix = prefix_raw[:3].ljust(3, 'X') if prefix_raw else 'EMP'

            users = CustomUser.objects.filter(
                organization=org
            ).order_by('date_joined')

            counter = 0
            for user in users:
                counter += 1
                changed = False

                if not user.joined_date and user.date_joined:
                    user.joined_date = user.date_joined.date()
                    fixed_dates += 1
                    changed = True

                if not user.employee_id:
                    candidate = f"{prefix}-{str(counter).zfill(4)}"
                    # Avoid collisions
                    while CustomUser.objects.filter(
                        employee_id=candidate
                    ).exclude(id=user.id).exists():
                        counter += 1
                        candidate = f"{prefix}-{str(counter).zfill(4)}"
                    user.employee_id = candidate
                    fixed_ids += 1
                    changed = True

                if changed:
                    user.save()

            # Update org counter to max
            if counter > org.emp_id_counter:
                org.emp_id_counter = counter
                org.save()

        self.stdout.write(
            self.style.SUCCESS(
                f'Done. Fixed {fixed_dates} joined dates, '
                f'{fixed_ids} employee IDs.'
            )
        )