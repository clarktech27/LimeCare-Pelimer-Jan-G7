from django.conf import settings
from django.db import models


class Profile(models.Model):
    ADMIN = 'admin'
    STAFF = 'staff'
    ROLE_CHOICES = [(ADMIN, 'Admin'), (STAFF, 'Staff')]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=STAFF)
    contact_number = models.CharField(max_length=20, blank=True)

    def __str__(self):
        return f'{self.user.username} ({self.role})'

    @property
    def is_admin(self):
        return self.role == self.ADMIN
