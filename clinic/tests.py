import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import Department, Profile

from .models import Patient

User = get_user_model()
PW = 'pw12345!x'


def make_user(username, role):
    user = User.objects.create_user(username, f'{username}@x.com', PW)
    dept = Department.objects.get_or_create(name='General')[0]
    user.profile.role = role
    user.profile.department = dept
    user.profile.save()
    return user


GOOD = dict(
    first_name='Maria', middle_name='', last_name='Santos', birth_date='1990-05-20', sex='Female',
    contact_number='0917 123 4567', email='', address='Cebu City',
    emergency_contact_name='', emergency_contact_number='',
)


class PatientAccessTests(TestCase):
    def setUp(self):
        self.reg = make_user('reg', Profile.REGISTRATION)
        self.doc = make_user('doc', Profile.DOCTOR)

    def test_anonymous_redirected_to_login(self):
        r = self.client.get(reverse('clinic:patient_list'))
        self.assertEqual(r.status_code, 302)
        self.assertIn(reverse('accounts:login'), r.url)

    def test_doctor_can_view_but_not_register(self):
        self.client.login(username='doc', password=PW)
        self.assertEqual(self.client.get(reverse('clinic:patient_list')).status_code, 200)
        self.assertEqual(self.client.get(reverse('clinic:patient_create')).status_code, 403)
        self.assertEqual(self.client.post(reverse('clinic:patient_create'), GOOD).status_code, 403)
        self.assertEqual(Patient.objects.count(), 0)


class PatientCrudTests(TestCase):
    def setUp(self):
        self.reg = make_user('reg', Profile.REGISTRATION)
        self.client.login(username='reg', password=PW)

    def test_create_generates_number_and_links_user(self):
        r = self.client.post(reverse('clinic:patient_create'), GOOD, follow=True)
        p = Patient.objects.get()
        self.assertEqual(p.registered_by, self.reg)
        self.assertEqual(p.patient_number, f'LC-{timezone.localdate().year}-00001')
        self.assertContains(r, 'was registered as')

    def test_numbers_increase(self):
        self.client.post(reverse('clinic:patient_create'), GOOD)
        self.client.post(reverse('clinic:patient_create'), {**GOOD, 'first_name': 'Ana'})
        self.assertEqual(Patient.objects.filter(patient_number__endswith='00002').count(), 1)

    def test_validation(self):
        url = reverse('clinic:patient_create')
        future = (timezone.localdate() + datetime.timedelta(days=1)).isoformat()
        for bad in [{'first_name': ''}, {'birth_date': future}, {'contact_number': 'abc'}, {'address': ''}, {'sex': 'X'}]:
            r = self.client.post(url, {**GOOD, **bad})
            self.assertEqual(r.status_code, 200)
            self.assertContains(r, 'Please correct the errors below')
        self.assertEqual(Patient.objects.count(), 0)

    def test_duplicate_identity_rejected_case_insensitive(self):
        url = reverse('clinic:patient_create')
        self.client.post(url, GOOD)
        r = self.client.post(url, {**GOOD, 'first_name': 'MARIA', 'last_name': 'santos'})
        self.assertContains(r, 'already registered')
        self.assertEqual(Patient.objects.count(), 1)

    def test_edit_keeps_patient_number(self):
        self.client.post(reverse('clinic:patient_create'), GOOD)
        p = Patient.objects.get()
        number = p.patient_number
        r = self.client.post(reverse('clinic:patient_edit', args=[p.pk]),
                             {**GOOD, 'address': 'Mandaue City', 'patient_number': 'HACK'}, follow=True)
        p.refresh_from_db()
        self.assertEqual((p.address, p.patient_number), ('Mandaue City', number))
        self.assertContains(r, 'updated successfully')

    def test_deactivate_and_reactivate_never_deletes(self):
        self.client.post(reverse('clinic:patient_create'), GOOD)
        p = Patient.objects.get()
        url = reverse('clinic:patient_toggle_active', args=[p.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        self.client.post(url)
        p.refresh_from_db()
        self.assertFalse(p.is_active)
        self.client.post(url)
        p.refresh_from_db()
        self.assertTrue(p.is_active)

    def test_search_and_status_filter(self):
        Patient.objects.create(**{**GOOD, 'birth_date': datetime.date(1990, 5, 20)}, registered_by=self.reg)
        Patient.objects.create(**{**GOOD, 'first_name': 'Jose', 'last_name': 'Reyes',
                                  'birth_date': datetime.date(1985, 1, 2)}, registered_by=self.reg)
        url = reverse('clinic:patient_list')
        r = self.client.get(url, {'q': 'maria santos'})
        self.assertContains(r, 'Santos'); self.assertNotContains(r, 'Reyes')
        self.assertContains(self.client.get(url, {'q': 'LC-'}), 'Reyes')
        Patient.objects.filter(last_name='Reyes').update(is_active=False)
        self.assertNotContains(self.client.get(url), 'Reyes')
        self.assertContains(self.client.get(url, {'status': 'inactive'}), 'Reyes')