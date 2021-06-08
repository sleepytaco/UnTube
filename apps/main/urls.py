from django.conf.urls import url
from django.urls import path
from . import views

urlpatterns = [
    path("home/", views.home, name='home'),
    # path("", views.index, name='index'),
    # path("login/", views.log_in, name='log_in'),

    ### STUFF RELATED TO WHOLE SITE
    path("search/UnTube/", views.search_UnTube, name="search_UnTube"),

    ### STUFF RELATED TO ONE VIDEO
    path("<slug:playlist_id>/<slug:video_id>/video-details", views.view_video, name='video_details'),
    path("<slug:playlist_id>/<slug:video_id>/video-details/notes", views.video_notes, name='video_notes'),
    path("<slug:playlist_id>/<slug:video_id>/video-details/favorite", views.mark_video_favortie, name='mark_video_favorite'),
    path("delete-videos", views.delete_videos, name='delete_videos'),

    ### STUFF RELATED TO ONE PLAYLIST
    path("playlist/<slug:playlist_id>", views.view_playlist, name='playlist'),
    path("playlist/<slug:playlist_id>/order-by/<slug:order_by>", views.order_playlist_by,
         name='order_playlist_by'),
    path("playlist/<slug:playlist_id>/mark-as/<slug:mark_as>", views.mark_playlist_as,
         name='mark_playlist_as'),

    ### STUFF RELATED TO PLAYLISTS IN BULK
    path("search/playlists/<slug:playlist_type>", views.search_playlists, name="search_playlists"),
    path("playlists/<slug:playlist_type>", views.all_playlists, name='all_playlists'),
    path("playlists/<slug:playlist_type>/order-by/<slug:order_by>", views.order_playlists_by, name='order_playlists_by'),
]
