from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Profile


@receiver(post_save, sender=get_user_model())
def ensure_profile(sender, instance, created, **kwargs):
    # Self-registered users are Staff; superusers (createsuperuser) are Admin.
    if created:
        Profile.objects.create(
            user=instance,
            role=Profile.ADMIN if instance.is_superuser else Profile.STAFF,
        )
    else:
        Profile.objects.get_or_create(
            user=instance,
            defaults={'role': Profile.ADMIN if instance.is_superuser else Profile.STAFF},
        )
