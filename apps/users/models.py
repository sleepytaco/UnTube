import re
from django.contrib.auth.hashers import make_password, check_password

from django.db import models
from django.contrib.auth.models import User
from django.db.models import Count, Q
from django.db.models.signals import post_save
from django.dispatch import receiver


# Create your models here.
class ProfileManager(models.Manager):
    def updateUserProfile(self, details):
        pass


class Untube(models.Model):
    page_likes = models.IntegerField(default=0)


# extension of the built in User model made by Django
class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # settings
    robohash_set = models.IntegerField(default=3)  # determines profile picture from https://robohash.org/
    user_summary = models.CharField(max_length=300, default="I think my arm is on backward.")
    user_location = models.CharField(max_length=100, default="Hell, Earth")

    ### GLOBAL preferences ###
    # site preferences
    open_search_new_tab = models.BooleanField(default=True)  # open search page in new tab by default
    enable_gradient_bg = models.BooleanField(default=False)

    # playlist preferences (this will apply to all playlists)
    auto_check_for_updates = models.BooleanField(default=False)
    hide_unavailable_videos = models.BooleanField(default=True)
    confirm_before_deleting = models.BooleanField(default=True)
    ###########################

    # manage user
    objects = ProfileManager()
    show_import_page = models.BooleanField(default=True)  # shows the user tips for a week
    yt_channel_id = models.CharField(max_length=420, default='')
    import_in_progress = models.BooleanField(
        default=False)  # if True, will not let the user access main site until they import their YT playlists
    imported_yt_playlists = models.BooleanField(default=False)  # True if user imported all their YT playlists

    # google api token details
    access_token = models.TextField(default="")
    refresh_token = models.TextField(default="")
    expires_at = models.DateTimeField(blank=True, null=True)

    # import playlist page
    manage_playlists_import_textarea = models.CharField(max_length=420, default="")

    # create playlist page
    create_playlist_name = models.CharField(max_length=50, default="")
    create_playlist_desc = models.CharField(max_length=50, default="")
    create_playlist_type = models.CharField(max_length=50, default="")
    create_playlist_add_vids_from_collection = models.CharField(max_length=50, default="")
    create_playlist_add_vids_from_links = models.CharField(max_length=50, default="")

    def get_channels_list(self):
        channels_list = []
        videos = self.user.videos.filter(Q(is_unavailable_on_yt=False) & Q(was_deleted_on_yt=False))

        queryset = videos.values(
            'channel_name').annotate(channel_videos_count=Count('video_id')).order_by('-channel_videos_count')

        for entry in queryset:
            channels_list.append(entry['channel_name'])

        return channels_list

    def get_playlists_list(self):
        return self.user.playlists.all().filter(is_in_db=True)

# as soon as one User object is created, create an associated profile object
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)


# whenever User.save() happens, Profile.save() also happens
@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    instance.profile.save()
