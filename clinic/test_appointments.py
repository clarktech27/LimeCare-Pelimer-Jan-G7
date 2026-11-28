import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import Department, DoctorProfile, Profile

from .models import Appointment, Patient

User = get_user_model()
PW = 'pw12345!x'


def make_user(username, role, department=None):
    user = User.objects.create_user(username, f'{username}@x.com', PW, first_name=username.title(), last_name='Test')
    user.profile.role = role
    user.profile.department = department
    user.profile.save()
    return user


def make_doctor(username, department, license_number):
    user = make_user(username, Profile.DOCTOR, department)
    return DoctorProfile.objects.create(user=user, specialization='General', license_number=license_number)


def future(days=2, hour=10, minute=0):
    base = timezone.localtime() + datetime.timedelta(days=days)
    return base.replace(hour=hour, minute=minute, second=0, microsecond=0)


def stamp(value):
    return value.strftime('%Y-%m-%dT%H:%M')


class AppointmentBase(TestCase):
    def setUp(self):
        self.peds = Department.objects.create(name='Pediatrics')
        self.cardio = Department.objects.create(name='Cardiology')
        self.reg = make_user('reg', Profile.REGISTRATION)
        self.reg2 = make_user('reg2', Profile.REGISTRATION)
        self.admin = make_user('boss', Profile.ADMIN)
        self.nurse = make_user('nurse', Profile.NURSE, self.peds)
        self.doc = make_doctor('doc', self.peds, 'LIC-1')
        self.doc2 = make_doctor('doc2', self.peds, 'LIC-2')
        self.cardiologist = make_doctor('heart', self.cardio, 'LIC-3')
        self.patient = Patient.objects.create(
            first_name='Maria', last_name='Santos', birth_date=datetime.date(1990, 5, 20), sex='Female',
            contact_number='09171234567', address='Cebu', registered_by=self.reg,
        )
        self.patient2 = Patient.objects.create(
            first_name='Jose', last_name='Reyes', birth_date=datetime.date(1985, 1, 2), sex='Male',
            contact_number='09171234568', address='Cebu', registered_by=self.reg,
        )

    def login(self, user):
        self.client.login(username=user.username, password=PW)

    def payload(self, **overrides):
        data = {
            'patient': self.patient.pk, 'department': self.peds.pk, 'doctor': self.doc.pk,
            'scheduled_at': stamp(future()), 'reason': 'Check-up',
        }
        data.update(overrides)
        return data

    def book(self, **overrides):
        return self.client.post(reverse('clinic:appointment_create'), self.payload(**overrides))

    def make_appointment(self, when=None, doctor=None, patient=None, by=None, status=Appointment.SCHEDULED):
        return Appointment.objects.create(
            patient=patient or self.patient, doctor=doctor or self.doc, department=self.peds,
            scheduled_at=when or future(), created_by=by or self.reg, status=status,
        )


class AppointmentAccessTests(AppointmentBase):
    def test_anonymous_redirected_to_login(self):
        for name in ['appointment_list', 'appointment_create']:
            r = self.client.get(reverse(f'clinic:{name}'))
            self.assertEqual(r.status_code, 302)
            self.assertIn(reverse('accounts:login'), r.url)

    def test_nurse_has_no_access(self):
        self.login(self.nurse)
        self.assertEqual(self.client.get(reverse('clinic:appointment_list')).status_code, 403)
        self.assertEqual(self.client.get(reverse('clinic:appointment_create')).status_code, 403)

    def test_doctor_sees_only_own_schedule_and_cannot_book(self):
        mine = self.make_appointment(doctor=self.doc)
        other = self.make_appointment(doctor=self.doc2, patient=self.patient2)
        self.login(self.doc.user)
        r = self.client.get(reverse('clinic:appointment_list'))
        self.assertContains(r, 'Maria Santos')
        self.assertNotContains(r, 'Jose Reyes')
        self.assertEqual(self.client.get(reverse('clinic:appointment_detail', args=[mine.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse('clinic:appointment_detail', args=[other.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse('clinic:appointment_create')).status_code, 403)
        self.assertEqual(self.book().status_code, 403)

    def test_registration_sees_all_but_modifies_only_own(self):
        appt = self.make_appointment(by=self.reg)
        self.login(self.reg2)
        self.assertContains(self.client.get(reverse('clinic:appointment_list')), 'Maria Santos')
        self.assertEqual(self.client.get(reverse('clinic:appointment_detail', args=[appt.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse('clinic:appointment_edit', args=[appt.pk])).status_code, 403)
        r = self.client.post(reverse('clinic:appointment_status', args=[appt.pk]), {'action': 'cancel'})
        self.assertEqual(r.status_code, 403)
        appt.refresh_from_db()
        self.assertEqual(appt.status, Appointment.SCHEDULED)

    def test_admin_can_modify_any(self):
        appt = self.make_appointment(by=self.reg)
        self.login(self.admin)
        self.client.post(reverse('clinic:appointment_status', args=[appt.pk]), {'action': 'cancel'})
        appt.refresh_from_db()
        self.assertEqual(appt.status, Appointment.CANCELLED)


class AppointmentBookingTests(AppointmentBase):
    def setUp(self):
        super().setUp()
        self.login(self.reg)

    def test_book_success_links_user(self):
        r = self.client.post(reverse('clinic:appointment_create'), self.payload(), follow=True)
        appt = Appointment.objects.get()
        self.assertEqual(appt.created_by, self.reg)
        self.assertEqual(appt.status, Appointment.SCHEDULED)
        self.assertContains(r, 'Appointment booked successfully')

    def test_required_fields(self):
        for field in ['patient', 'department', 'doctor', 'scheduled_at']:
            r = self.book(**{field: ''})
            self.assertEqual(r.status_code, 200)
            self.assertContains(r, 'Please correct the errors below')
        self.assertEqual(Appointment.objects.count(), 0)

    def test_br14_must_be_in_future(self):
        past = timezone.localtime() - datetime.timedelta(days=1)
        r = self.book(scheduled_at=stamp(past))
        self.assertContains(r, 'must be scheduled for a future date and time')
        self.assertEqual(Appointment.objects.count(), 0)

    def test_br15_doctor_must_belong_to_department(self):
        r = self.book(doctor=self.cardiologist.pk)
        self.assertContains(r, 'does not belong to the selected department')
        self.assertEqual(Appointment.objects.count(), 0)

    def test_br16_doctor_cannot_be_double_booked(self):
        self.book()
        r = self.book(patient=self.patient2.pk)
        self.assertContains(r, 'already has a Scheduled appointment at that date and time')
        self.assertEqual(Appointment.objects.count(), 1)

    def test_br16_slot_is_free_again_after_cancel(self):
        first = self.make_appointment(when=future())
        first.change_status(Appointment.CANCELLED)
        self.book(patient=self.patient2.pk)
        self.assertEqual(Appointment.objects.filter(status=Appointment.SCHEDULED).count(), 1)

    def test_br17_one_scheduled_per_patient_doctor_day(self):
        self.book()
        r = self.book(scheduled_at=stamp(future(hour=15)))
        self.assertContains(r, 'already has a Scheduled appointment with this doctor on that day')
        self.assertEqual(Appointment.objects.count(), 1)
        # a different doctor on the same day is fine
        self.book(doctor=self.doc2.pk, scheduled_at=stamp(future(hour=15)))
        self.assertEqual(Appointment.objects.count(), 2)

    def test_inactive_patient_cannot_be_booked(self):
        self.patient.is_active = False
        self.patient.save()
        r = self.book()
        self.assertContains(r, 'Please correct the errors below')
        self.assertEqual(Appointment.objects.count(), 0)

    def test_prefill_from_patient_page(self):
        r = self.client.get(reverse('clinic:appointment_create'), {'patient': self.patient.pk})
        self.assertContains(r, f'value="{self.patient.pk}" selected')


class AppointmentUpdateTests(AppointmentBase):
    def setUp(self):
        super().setUp()
        self.login(self.reg)
        self.appt = self.make_appointment()

    def test_reschedule(self):
        new_time = future(days=5, hour=14)
        r = self.client.post(
            reverse('clinic:appointment_edit', args=[self.appt.pk]),
            self.payload(scheduled_at=stamp(new_time), reason='Follow-up'), follow=True,
        )
        self.appt.refresh_from_db()
        self.assertEqual(timezone.localtime(self.appt.scheduled_at), new_time)
        self.assertEqual(self.appt.reason, 'Follow-up')
        self.assertContains(r, 'rescheduled successfully')

    def test_reschedule_applies_rules_and_keeps_patient(self):
        other = self.make_appointment(when=future(days=3), patient=self.patient2)
        r = self.client.post(
            reverse('clinic:appointment_edit', args=[self.appt.pk]),
            self.payload(scheduled_at=stamp(future(days=3)), patient=self.patient2.pk),
        )
        self.assertContains(r, 'already has a Scheduled appointment at that date and time')
        self.appt.refresh_from_db()
        self.assertEqual(self.appt.patient, self.patient)
        self.assertEqual(other.status, Appointment.SCHEDULED)

    def test_br18_status_changes_are_one_way(self):
        url = reverse('clinic:appointment_status', args=[self.appt.pk])
        self.client.post(url, {'action': 'complete'})
        self.appt.refresh_from_db()
        self.assertEqual(self.appt.status, Appointment.COMPLETED)
        r = self.client.post(url, {'action': 'cancel'}, follow=True)
        self.appt.refresh_from_db()
        self.assertEqual(self.appt.status, Appointment.COMPLETED)
        self.assertContains(r, 'Only Scheduled appointments can be changed')

    def test_cancel_and_no_show(self):
        other = self.make_appointment(when=future(days=3), patient=self.patient2)
        self.client.post(reverse('clinic:appointment_status', args=[self.appt.pk]), {'action': 'cancel'})
        self.client.post(reverse('clinic:appointment_status', args=[other.pk]), {'action': 'no_show'})
        self.appt.refresh_from_db(); other.refresh_from_db()
        self.assertEqual((self.appt.status, other.status), (Appointment.CANCELLED, Appointment.NO_SHOW))

    def test_cannot_reschedule_closed_appointment(self):
        self.appt.change_status(Appointment.CANCELLED)
        r = self.client.get(reverse('clinic:appointment_edit', args=[self.appt.pk]), follow=True)
        self.assertContains(r, 'Only Scheduled appointments can be rescheduled')

    def test_status_requires_post(self):
        r = self.client.get(reverse('clinic:appointment_status', args=[self.appt.pk]))
        self.assertEqual(r.status_code, 405)

    def test_invalid_action_changes_nothing(self):
        self.client.post(reverse('clinic:appointment_status', args=[self.appt.pk]), {'action': 'bogus'})
        self.appt.refresh_from_db()
        self.assertEqual(self.appt.status, Appointment.SCHEDULED)


class AppointmentListAndDashboardTests(AppointmentBase):
    def test_filters_and_search(self):
        self.make_appointment(when=future(days=2))
        cancelled = self.make_appointment(when=future(days=3), patient=self.patient2, status=Appointment.CANCELLED)
        self.login(self.reg)
        url = reverse('clinic:appointment_list')
        r = self.client.get(url)
        self.assertContains(r, 'Santos'); self.assertNotContains(r, 'Reyes')
        self.assertContains(self.client.get(url, {'status': 'Cancelled'}), 'Reyes')
        self.assertContains(self.client.get(url, {'status': 'all'}), 'Reyes')
        self.assertContains(self.client.get(url, {'q': 'LC-', 'status': 'all'}), 'Santos')
        r = self.client.get(url, {'date': cancelled.scheduled_at.astimezone().date().isoformat(), 'status': 'all'})
        self.assertContains(r, 'Reyes'); self.assertNotContains(r, 'Santos')

    def test_dashboards_show_appointment_data(self):
        self.make_appointment()
        self.login(self.reg)
        r = self.client.get(reverse('accounts:staff_dashboard'))
        self.assertEqual(r.context['upcoming_count'], 1)
        self.client.logout()
        self.login(self.doc2.user)
        self.assertEqual(self.client.get(reverse('accounts:staff_dashboard')).context['upcoming_count'], 0)
        self.client.logout()
        self.login(self.doc.user)
        self.assertEqual(self.client.get(reverse('accounts:staff_dashboard')).context['upcoming_count'], 1)
        self.client.logout()
        self.login(self.admin)
        r = self.client.get(reverse('accounts:admin_dashboard'))
        self.assertEqual(r.context['scheduled_count'], 1)
        self.assertEqual(r.context['patient_count'], 2)
        self.client.logout()
        self.login(self.nurse)
        self.assertEqual(self.client.get(reverse('accounts:staff_dashboard')).status_code, 200)