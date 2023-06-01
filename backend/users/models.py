from allauth.socialaccount.models import SocialToken
from django.conf import settings
from django.contrib.auth.models import User
from django.db import models
from django.db.models import Count, Q
from django.db.models.signals import post_save
from django.dispatch import receiver
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials


class Untube(models.Model):
    page_likes = models.IntegerField(default=0)


# extension of the built in User model made by Django
class Profile(models.Model):
    untube_user = models.OneToOneField(User, on_delete=models.CASCADE)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # settings
    robohash_set = models.IntegerField(default=3)  # determines profile picture from https://robohash.org/
    user_summary = models.CharField(max_length=300, default='I think my arm is on backward.')
    user_location = models.CharField(max_length=100, default='Hell, Earth')

    # GLOBAL preferences
    # site preferences
    open_search_new_tab = models.BooleanField(default=True)  # open search page in new tab by default
    enable_gradient_bg = models.BooleanField(default=False)

    # playlist preferences (this will apply to all playlists)
    hide_unavailable_videos = models.BooleanField(default=True)
    confirm_before_deleting = models.BooleanField(default=True)
    ###########################

    # manage user
    show_import_page = models.BooleanField(default=True)  # shows the user tips for a week
    yt_channel_id = models.TextField(default='')
    import_in_progress = models.BooleanField(
        default=False
    )  # if True, will not let the user access main site until they import their YT playlists
    imported_yt_playlists = models.BooleanField(default=False)  # True if user imported all their YT playlists

    # google api token details
    access_token = models.TextField(default='')
    refresh_token = models.TextField(default='')
    expires_at = models.DateTimeField(blank=True, null=True)

    # import playlist page
    manage_playlists_import_textarea = models.TextField(default='')

    # create playlist page
    create_playlist_name = models.CharField(max_length=50, default='')
    create_playlist_desc = models.CharField(max_length=50, default='')
    create_playlist_type = models.CharField(max_length=50, default='')
    create_playlist_add_vids_from_collection = models.CharField(max_length=50, default='')
    create_playlist_add_vids_from_links = models.CharField(max_length=50, default='')

    def __str__(self):
        return f'{self.untube_user.username} ({self.untube_user.email})'

    def get_credentials(self):
        """
        Returns Google OAuth credentials object by using user's OAuth token
        """
        # if the profile model does not hold the tokens, retrieve them from user's SocialToken entry and save them into profile
        if self.access_token.strip() == '' or self.refresh_token.strip() == '':
            user_social_token = SocialToken.objects.get(account__user=self.untube_user)
            self.access_token = user_social_token.token
            self.refresh_token = user_social_token.token_secret
            self.expires_at = user_social_token.expires_at
            self.save(update_fields=['access_token', 'refresh_token', 'expires_at'])

        # app = SocialApp.objects.get(provider='google')
        credentials = Credentials(
            token=self.access_token,
            refresh_token=self.refresh_token,
            token_uri='https://oauth2.googleapis.com/token',
            client_id=settings.GOOGLE_OAUTH_CLIENT_ID,  # app.client_id,
            client_secret=settings.GOOGLE_OAUTH_CLIENT_SECRET,  # app.secret,
            scopes=['https://www.googleapis.com/auth/youtube']
        )

        if not credentials.valid:
            credentials.refresh(Request())
            self.access_token = credentials.token
            self.refresh_token = credentials.refresh_token
            self.save(update_fields=['access_token', 'refresh_token'])

        return credentials

    def get_channels_list(self):
        channels_list = []
        videos = self.untube_user.videos.filter(Q(is_unavailable_on_yt=False) & Q(was_deleted_on_yt=False))

        queryset = videos.values('channel_name').annotate(channel_videos_count=Count('video_id')
                                                          ).order_by('-channel_videos_count')

        for entry in queryset:
            channels_list.append(entry['channel_name'])

        return channels_list

    def get_playlists_list(self):
        return self.untube_user.playlists.all().filter(is_in_db=True)


# as soon as one User object is created, create an associated profile object
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(untube_user=instance)


# whenever User.save() happens, Profile.save() also happens
@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    instance.profile.save()
