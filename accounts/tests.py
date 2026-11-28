from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Profile

User = get_user_model()
GOOD = dict(first_name='Ana', last_name='Cruz', username='ana', email='ana@example.com',
            password1='Str0ng!Pass#9', password2='Str0ng!Pass#9')


class RegistrationTests(TestCase):
    def test_success_hashes_password_and_creates_staff(self):
        r = self.client.post(reverse('accounts:register'), GOOD, follow=True)
        u = User.objects.get(username='ana')
        self.assertTrue(u.password.startswith('pbkdf2_'))
        self.assertNotEqual(u.password, GOOD['password1'])
        self.assertEqual(u.profile.role, Profile.REGISTRATION)
        self.assertContains(r, 'Account created successfully')
        self.assertEqual(r.redirect_chain[-1][0], reverse('accounts:staff_dashboard'))

    def test_required_email_password_mismatch_duplicates(self):
        url = reverse('accounts:register')
        self.assertEqual(self.client.post(url, {**GOOD, 'email': ''}).status_code, 200)
        self.assertEqual(self.client.post(url, {**GOOD, 'email': 'bad'}).status_code, 200)
        self.assertEqual(self.client.post(url, {**GOOD, 'password2': 'nope'}).status_code, 200)
        self.assertEqual(User.objects.count(), 0)
        self.client.post(url, GOOD); self.client.logout()
        r = self.client.post(url, {**GOOD, 'username': 'other', 'email': 'ANA@example.com'})
        self.assertContains(r, 'already exists')
        r = self.client.post(url, {**GOOD, 'email': 'new@example.com'})
        self.assertContains(r, 'already exists')
        self.assertEqual(User.objects.count(), 1)


class AuthAndRoleTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user('s', 's@x.com', 'pw12345!x')
        self.admin = User.objects.create_superuser('a', 'a@x.com', 'pw12345!x')

    def test_profiles_and_roles(self):
        self.assertEqual(self.staff.profile.role, 'registration')
        self.assertEqual(self.admin.profile.role, 'admin')

    def test_invalid_login_message(self):
        r = self.client.post(reverse('accounts:login'), {'username': 's', 'password': 'wrong'})
        self.assertContains(r, 'Invalid username or password')

    def test_login_redirects_by_role(self):
        r = self.client.post(reverse('accounts:login'), {'username': 'a', 'password': 'pw12345!x'})
        self.assertRedirects(r, reverse('accounts:admin_dashboard'))
        self.client.logout()
        r = self.client.post(reverse('accounts:login'), {'username': 's', 'password': 'pw12345!x'})
        self.assertRedirects(r, reverse('accounts:staff_dashboard'))

    def test_logout_ends_session(self):
        self.client.login(username='s', password='pw12345!x')
        self.client.post(reverse('accounts:logout'))
        r = self.client.get(reverse('accounts:staff_dashboard'))
        self.assertEqual(r.status_code, 302)

    def test_anonymous_redirected_to_login(self):
        for n in ['home', 'admin_dashboard', 'staff_dashboard', 'profile', 'profile_edit']:
            r = self.client.get(reverse(f'accounts:{n}'))
            self.assertEqual(r.status_code, 302)
            self.assertIn(reverse('accounts:login'), r.url)

    def test_cross_role_access_forbidden(self):
        self.client.login(username='s', password='pw12345!x')
        self.assertEqual(self.client.get(reverse('accounts:admin_dashboard')).status_code, 403)
        self.client.login(username='a', password='pw12345!x')
        self.assertEqual(self.client.get(reverse('accounts:staff_dashboard')).status_code, 403)
        self.assertEqual(self.client.get(reverse('accounts:admin_dashboard')).status_code, 200)


class ProfileTests(TestCase):
    def setUp(self):
        self.u1 = User.objects.create_user('u1', 'u1@x.com', 'pw12345!x')
        self.u2 = User.objects.create_user('u2', 'u2@x.com', 'pw12345!x')
        self.client.login(username='u1', password='pw12345!x')

    def test_view_own_only(self):
        r = self.client.get(reverse('accounts:profile'))
        self.assertContains(r, 'u1@x.com'); self.assertNotContains(r, 'u2@x.com')

    def test_update(self):
        r = self.client.post(reverse('accounts:profile_edit'), dict(
            first_name='New', last_name='Name', email='new@x.com', contact_number='0917 123 4567'), follow=True)
        self.assertContains(r, 'Profile updated successfully')
        self.u1.refresh_from_db()
        self.assertEqual(self.u1.email, 'new@x.com'); self.assertEqual(self.u1.profile.contact_number, '0917 123 4567')

    def test_cannot_take_other_email_or_edit_other_user(self):
        r = self.client.post(reverse('accounts:profile_edit'), dict(
            first_name='A', last_name='B', email='u2@x.com', contact_number='', user=self.u2.pk))
        self.assertContains(r, 'already uses this email')
        self.u2.refresh_from_db(); self.assertEqual(self.u2.email, 'u2@x.com')

    def test_bad_phone(self):
        r = self.client.post(reverse('accounts:profile_edit'), dict(
            first_name='A', last_name='B', email='u1@x.com', contact_number='abc'))
        self.assertContains(r, 'valid contact number')
