from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class Department(models.Model):
    """Hospital department (e.g. Pediatrics). Never deleted, only deactivated (BR-28)."""
    name = models.CharField(max_length=80, unique=True)
    description = models.CharField(max_length=150, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Profile(models.Model):
    ADMIN = 'admin'
    DOCTOR = 'doctor'
    NURSE = 'nurse'
    REGISTRATION = 'registration'
    ROLE_CHOICES = [
        (ADMIN, 'Admin'),
        (DOCTOR, 'Doctor'),
        (NURSE, 'Nurse'),
        (REGISTRATION, 'Registration Staff'),
    ]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=REGISTRATION)
    department = models.ForeignKey(
        Department, on_delete=models.PROTECT, null=True, blank=True, related_name='staff_profiles',
    )
    contact_number = models.CharField(max_length=20, blank=True)

    def __str__(self):
        return f'{self.user.username} ({self.role})'

    def clean(self):
        # BR-07: doctors and nurses must belong to a department.
        if self.role in (self.DOCTOR, self.NURSE) and not self.department_id:
            raise ValidationError({'department': 'Doctors and nurses must be assigned to a department.'})

    @property
    def is_admin(self):
        return self.role == self.ADMIN

    @property
    def is_doctor(self):
        return self.role == self.DOCTOR

    @property
    def is_nurse(self):
        return self.role == self.NURSE

    @property
    def is_registration(self):
        return self.role == self.REGISTRATION


class DoctorProfile(models.Model):
    """Extra details for a user whose role is Doctor (BR-08)."""
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='doctor_profile')
    specialization = models.CharField(max_length=80)
    license_number = models.CharField(max_length=30, unique=True)

    def __str__(self):
        name = self.user.get_full_name() or self.user.username
        return f'Dr. {name}'

    def clean(self):
        if self.user_id and self.user.profile.role != Profile.DOCTOR:
            raise ValidationError({'user': 'The selected user does not have the Doctor role.'})

    @property
    def department(self):
        # Stored once, on the staff profile (SDD design note).
        return self.user.profile.department