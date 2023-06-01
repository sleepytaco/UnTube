from django.urls import path

from backend.charts import views

urlpatterns = [
    path(
        'channel-videos-distribution/<slug:playlist_id>',
        views.channel_videos_distribution,
        name='channel_videos_distribution'
    ),
    path(
        'overall-playlists-distribution/', views.overall_playlists_distribution, name='overall_playlists_distribution'
    ),
    path('overall-channels-distribution/', views.overall_channels_distribution, name='overall_channels_distribution'),
    path(
        'watching-playlists-percent-distribution/',
        views.watching_playlists_percent_distribution,
        name='watching_playlists_percent_distribution'
    ),
]
