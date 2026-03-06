from django.db import migrations


def backfill_employee_data(apps, schema_editor):
    Organization = apps.get_model('core', 'Organization')
    CustomUser = apps.get_model('core', 'CustomUser')

    for org in Organization.objects.all():
        # Build prefix from org name
        clean = ''.join(c for c in org.name.upper() if c.isalpha())
        prefix = clean[:3] if len(clean) >= 3 else clean.ljust(3, 'X')

        # Get users ordered by date_joined
        users = CustomUser.objects.filter(
            organization=org
        ).order_by('date_joined')

        counter = 0
        for user in users:
            counter += 1
            # Assign employee ID if not already set
            if not user.employee_id:
                user.employee_id = f"{prefix}-{str(counter).zfill(4)}"
            # Backfill joined_date from date_joined
            if not user.joined_date and user.date_joined:
                user.joined_date = user.date_joined.date()
            user.save()

        # Set org counter to highest assigned
        org.emp_id_counter = counter
        org.save()


def reverse_backfill(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
    ('core', '0013_remove_project_sop_file_remove_project_sop_link_and_more'),
]

    operations = [
        migrations.RunPython(backfill_employee_data, reverse_backfill),
    ]