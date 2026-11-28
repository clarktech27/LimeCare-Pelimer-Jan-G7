from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Profile


@receiver(post_save, sender=get_user_model())
def ensure_profile(sender, instance, created, **kwargs):
    # Self-registered users start as Registration Staff; superusers (createsuperuser) are Admin.
    # Admin can change a user's role (and department) afterwards.
    default_role = Profile.ADMIN if instance.is_superuser else Profile.REGISTRATION
    if created:
        Profile.objects.create(user=instance, role=default_role)
    else:
        Profile.objects.get_or_create(user=instance, defaults={'role': default_role})