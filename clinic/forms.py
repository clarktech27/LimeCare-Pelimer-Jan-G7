import re

from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from accounts.models import Department, DoctorProfile

from .models import Appointment, Patient

PHONE_RE = re.compile(r'^[0-9+\-\s()]{7,20}$')


class PatientForm(forms.ModelForm):
    class Meta:
        model = Patient
        fields = (
            'first_name', 'middle_name', 'last_name', 'birth_date', 'sex', 'contact_number',
            'email', 'address', 'emergency_contact_name', 'emergency_contact_number',
        )
        widgets = {'birth_date': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d')}

    def _clean_phone(self, name, label):
        value = self.cleaned_data[name].strip()
        if value and not PHONE_RE.match(value):
            raise ValidationError(f'Enter a valid {label}.')
        return value

    def clean_contact_number(self):
        return self._clean_phone('contact_number', 'contact number')

    def clean_emergency_contact_number(self):
        return self._clean_phone('emergency_contact_number', 'emergency contact number')

    def clean_first_name(self):
        return self.cleaned_data['first_name'].strip()

    def clean_last_name(self):
        return self.cleaned_data['last_name'].strip()

    def validate_constraints(self):
        # BR-12 is checked (case-insensitively) in clean(), so skip Django's duplicate message.
        pass

    def clean(self):
        data = super().clean()
        first, last, birth = data.get('first_name'), data.get('last_name'), data.get('birth_date')
        if first and last and birth:
            duplicate = Patient.objects.filter(
                first_name__iexact=first, last_name__iexact=last, birth_date=birth,
            ).exclude(pk=self.instance.pk)
            if duplicate.exists():
                raise ValidationError(
                    'A patient with the same first name, last name and birth date is already registered.'
                )
        return data


class DoctorSelect(forms.Select):
    """Adds each doctor's department id to the <option> so the page can filter doctors by department."""

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex, attrs)
        instance = getattr(value, 'instance', None)
        if instance is not None:
            option['attrs']['data-department'] = instance.user.profile.department_id or ''
        return option


class AppointmentForm(forms.ModelForm):
    class Meta:
        model = Appointment
        fields = ('patient', 'department', 'doctor', 'scheduled_at', 'reason')
        widgets = {
            'doctor': DoctorSelect,
            'scheduled_at': forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
        }
        labels = {'scheduled_at': 'Date and time', 'reason': 'Reason for visit'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['scheduled_at'].input_formats = ['%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M']
        # BR-13 / BR-28: inactive patients and departments cannot be chosen for new bookings.
        self.fields['patient'].queryset = Patient.objects.filter(is_active=True)
        self.fields['department'].queryset = Department.objects.filter(is_active=True)
        self.fields['doctor'].queryset = DoctorProfile.objects.filter(
            user__is_active=True, user__profile__department__is_active=True,
        ).select_related('user__profile__department').order_by('user__last_name', 'user__first_name')
        self.fields['doctor'].label_from_instance = (
            lambda d: f'Dr. {d.user.get_full_name() or d.user.username} ({d.specialization})'
        )
        if self.instance.pk:
            # Rescheduling: the patient stays the same.
            self.fields['patient'].queryset = Patient.objects.all()
            self.fields['patient'].disabled = True

    def validate_constraints(self):
        # BR-16 is checked in clean() with a friendlier message.
        pass

    def clean(self):
        data = super().clean()
        patient, doctor = data.get('patient'), data.get('doctor')
        department, when = data.get('department'), data.get('scheduled_at')

        if when and when <= timezone.now():  # BR-14
            self.add_error('scheduled_at', 'The appointment must be scheduled for a future date and time.')

        if doctor and department and doctor.user.profile.department_id != department.pk:  # BR-15
            self.add_error('doctor', 'The selected doctor does not belong to the selected department.')

        if doctor and when:  # BR-16
            taken = Appointment.objects.filter(
                doctor=doctor, scheduled_at=when, status=Appointment.SCHEDULED,
            ).exclude(pk=self.instance.pk)
            if taken.exists():
                self.add_error('scheduled_at', 'This doctor already has a Scheduled appointment at that date and time.')

        if patient and doctor and when:  # BR-17
            same_day = Appointment.objects.filter(
                patient=patient, doctor=doctor, status=Appointment.SCHEDULED,
                scheduled_at__date=timezone.localtime(when).date(),
            ).exclude(pk=self.instance.pk)
            if same_day.exists():
                self.add_error(
                    'patient', 'This patient already has a Scheduled appointment with this doctor on that day.'
                )
        return data