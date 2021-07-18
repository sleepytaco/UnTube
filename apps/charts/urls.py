from django.urls import path
from apps.charts import views

urlpatterns = [
    path('channel-videos-distribution/<slug:playlist_id>', views.channel_videos_distribution, name='channel_videos_distribution'),

    path('overall-playlists-distribution/', views.overall_playlists_distribution,
         name='overall_playlists_distribution'),

]