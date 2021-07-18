from django.conf.urls import url
from django.urls import path
from . import views

urlpatterns = [
    path("home/", views.home, name='home'),
    # path("", views.index, name='index'),
    # path("login/", views.log_in, name='log_in'),

    ### STUFF RELATED TO INDIVIDUAL VIDEOS
    path("video/<slug:video_id>", views.view_video, name='video'),
    path("video/<slug:video_id>/notes", views.video_notes, name='video_notes'),

    ### STUFF RELATED TO WHOLE SITE
    path("search", views.search, name="search"),
    path("search/UnTube/", views.search_UnTube, name="search_UnTube"),

    ### STUFF RELATED TO VIDEO(S) INSIDE PLAYLISTS
    path("<slug:playlist_id>/<slug:video_id>/video-details", views.view_video, name='video_details'),
    path("<slug:playlist_id>/<slug:video_id>/video-details/favorite", views.mark_video_favortie, name='mark_video_favorite'),
    path('<slug:playlist_id>/<slug:video_id>/video-details/watched', views.mark_video_watched, name='mark_video_watched'),
    path("from/<slug:playlist_id>/delete-videos/<slug:command>", views.delete_videos, name='delete_videos'),
    path("videos/<slug:videos_type>", views.all_videos, name='all_videos'),

    ### STUFF RELATED TO ONE PLAYLIST
    path("playlist/<slug:playlist_id>", views.view_playlist, name='playlist'),
    path("playlist/<slug:playlist_id>/settings", views.view_playlist_settings, name="view_playlist_settings"),
    path("playlist/<slug:playlist_id>/order-by/<slug:order_by>", views.order_playlist_by,
         name='order_playlist_by'),
    path("playlist/<slug:playlist_id>/mark-as/<slug:mark_as>", views.mark_playlist_as,
         name='mark_playlist_as'),
    path("playlist/<slug:playlist_id>/update/<slug:type>", views.update_playlist, name="update_playlist"),
    path("playlist/<slug:playlist_id>/update-settings", views.update_playlist_settings, name="update_playlist_settings"),
    path("playlist/<slug:playlist_id>/<slug:order_by>/load-more-videos/<int:page>", views.load_more_videos, name="load_more_videos"),
    path("playlist/<slug:playlist_id>/create-tag", views.create_playlist_tag, name="create_playlist_tag"),
    path("playlist/<slug:playlist_id>/add-tag", views.add_playlist_tag, name="add_playlist_tag"),
    path("playlist/<slug:playlist_id>/remove-tag/<str:tag_name>", views.remove_playlist_tag, name="remove_playlist_tag"),
    path("playlist/<slug:playlist_id>/get-tags", views.get_playlist_tags, name="get_playlist_tags"),
    path("playlist/<slug:playlist_id>/get-unused-tags", views.get_unused_playlist_tags, name="get_unused_playlist_tags"),
    path("playlist/<slug:playlist_id>/get-watch-message", views.get_watch_message, name="get_watch_message"),
    path("playlist/<slug:playlist_id>/delete", views.delete_playlist, name="delete_playlist"),
    path("playlist/<slug:playlist_id>/reset-watched", views.reset_watched, name="reset_watched"),

    ### STUFF RELATED TO PLAYLISTS IN BULK
    path("search/playlists/<slug:playlist_type>", views.search_playlists, name="search_playlists"),
    path("playlists/<slug:playlist_type>", views.all_playlists, name='all_playlists'),
    path("playlists/<slug:playlist_type>/order-by/<slug:order_by>", views.order_playlists_by, name='order_playlists_by'),
    path("search/tagged-playlists/<str:tag>", views.search_tagged_playlists, name="search_tagged_playlists"),
    path("playlists/tag/<str:tag>", views.tagged_playlists, name='tagged_playlists'),

    ### STUFF RELATED TO MANAGING A PLAYLIST
    path("manage", views.manage_playlists, name='manage_playlists'),
    path("manage/save/<slug:what>", views.manage_save, name='manage_save'),  # to help auto save the input texts found in the below pages
    path("manage/view/<slug:page>", views.manage_view_page, name='manage_view_page'),  # views the import pl, create pl, create untube pl pages
    path("manage/import", views.manage_import_playlists, name="manage_import_playlists"),
    path("manage/create", views.manage_create_playlist, name="manage_create_playlist")
]
