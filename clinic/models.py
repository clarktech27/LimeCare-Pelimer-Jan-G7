from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.db.models import Q

def validate_not_future(value):
    # BR-10: the birth date cannot be in the future.
    if value > timezone.localdate():
        raise ValidationError('Birth date cannot be in the future.')


class Patient(models.Model):
    MALE = 'Male'
    FEMALE = 'Female'
    SEX_CHOICES = [(MALE, 'Male'), (FEMALE, 'Female')]

    # BR-11: system-generated, unique, cannot be edited (format LC-YYYY-00001).
    patient_number = models.CharField(max_length=15, unique=True, editable=False)
    first_name = models.CharField(max_length=50)
    middle_name = models.CharField(max_length=50, blank=True)
    last_name = models.CharField(max_length=50)
    birth_date = models.DateField(validators=[validate_not_future])
    sex = models.CharField(max_length=6, choices=SEX_CHOICES)
    contact_number = models.CharField(max_length=20)
    email = models.EmailField(max_length=100, blank=True)
    address = models.CharField(max_length=255)
    emergency_contact_name = models.CharField(max_length=100, blank=True)
    emergency_contact_number = models.CharField(max_length=20, blank=True)
    # BR-13: patients are deactivated, never deleted.
    is_active = models.BooleanField(default=True)
    registered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='registered_patients',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['last_name', 'first_name']
        constraints = [
            # BR-12: no two patients with the same last name, first name and birth date.
            models.UniqueConstraint(
                fields=['last_name', 'first_name', 'birth_date'], name='unique_patient_identity',
            ),
        ]

    def __str__(self):
        return f'{self.patient_number} - {self.full_name}'

    @property
    def full_name(self):
        parts = [self.first_name, self.middle_name, self.last_name]
        return ' '.join(p for p in parts if p)

    @property
    def age(self):
        today = timezone.localdate()
        years = today.year - self.birth_date.year
        if (today.month, today.day) < (self.birth_date.month, self.birth_date.day):
            years -= 1
        return years

    @classmethod
    def _next_number(cls):
        prefix = f'LC-{timezone.localdate().year}-'
        last = cls.objects.filter(patient_number__startswith=prefix).order_by('-patient_number').first()
        seq = int(last.patient_number.rsplit('-', 1)[1]) + 1 if last else 1
        return f'{prefix}{seq:05d}'

    def save(self, *args, **kwargs):
        if not self.patient_number:
            self.patient_number = self._next_number()
        super().save(*args, **kwargs)

        

class Appointment(models.Model):
    SCHEDULED = 'Scheduled'
    COMPLETED = 'Completed'
    CANCELLED = 'Cancelled'
    NO_SHOW = 'No-show'
    STATUS_CHOICES = [
        (SCHEDULED, 'Scheduled'),
        (COMPLETED, 'Completed'),
        (CANCELLED, 'Cancelled'),
        (NO_SHOW, 'No-show'),
    ]

    patient = models.ForeignKey(Patient, on_delete=models.PROTECT, related_name='appointments')
    doctor = models.ForeignKey('accounts.DoctorProfile', on_delete=models.PROTECT, related_name='appointments')
    department = models.ForeignKey('accounts.Department', on_delete=models.PROTECT, related_name='appointments')
    scheduled_at = models.DateTimeField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=SCHEDULED)
    reason = models.CharField(max_length=255, blank=True)
    # The staff member who booked the appointment.
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='booked_appointments',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['scheduled_at']
        constraints = [
            # BR-16: a doctor cannot have two Scheduled appointments at the same date and time.
            models.UniqueConstraint(
                fields=['doctor', 'scheduled_at'],
                condition=Q(status='Scheduled'),
                name='unique_scheduled_doctor_slot',
            ),
        ]

    def __str__(self):
        return f'{self.patient.full_name} with {self.doctor} on {timezone.localtime(self.scheduled_at):%Y-%m-%d %H:%M}'

    @property
    def badge_class(self):
        return {
            self.SCHEDULED: 'badge-blue',
            self.COMPLETED: 'badge-green',
            self.CANCELLED: 'badge-red',
        }.get(self.status, 'badge-grey')

    def change_status(self, new_status):
        """BR-18: Scheduled can become Completed, Cancelled or No-show; it can never go back."""
        if self.status != self.SCHEDULED:
            raise ValidationError(
                f'Only Scheduled appointments can be changed. This appointment is already {self.status}.'
            )
        if new_status not in (self.COMPLETED, self.CANCELLED, self.NO_SHOW):
            raise ValidationError('Invalid status change.')
        self.status = new_status
        self.save(update_fields=['status', 'updated_at'])