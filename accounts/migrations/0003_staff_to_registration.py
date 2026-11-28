from django.db import migrations


def staff_to_registration(apps, schema_editor):
    Profile = apps.get_model('accounts', 'Profile')
    Profile.objects.filter(role='staff').update(role='registration')


def registration_to_staff(apps, schema_editor):
    Profile = apps.get_model('accounts', 'Profile')
    Profile.objects.filter(role='registration').update(role='staff')


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0002_roles_departments_doctors'),
    ]

    operations = [
        migrations.RunPython(staff_to_registration, registration_to_staff),
    ]