import re
from django.contrib.auth.hashers import make_password, check_password

from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver


# Create your models here.
class ProfileManager(models.Manager):
    def updateUserProfile(self, details):
        pass


# extension of the built in User model made by Django
class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # manage user
    objects = ProfileManager()
    just_joined = models.BooleanField(default=True)
    yt_channel_id = models.CharField(max_length=420, default='')
    import_in_progress = models.BooleanField(default=True)

    # google api token details
    access_token = models.TextField(default="")
    refresh_token = models.TextField(default="")
    expires_at = models.DateTimeField(blank=True, null=True)

    # website contexts
    manage_playlists_import_textarea = models.CharField(max_length=420, default="")


# as soon as one User object is created, create an associated profile object
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)


# whenever User.save() happens, Profile.save() also happens
@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    instance.profile.save()
