import re

from django import forms
from django.core.exceptions import ValidationError

from .models import Patient

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