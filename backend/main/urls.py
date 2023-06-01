from django.urls import path

from . import views

urlpatterns = [

    # STUFF RELATED TO WHOLE SITE
    path('home/', views.home, name='home'),
    path('favorites', views.favorites, name='favorites'),
    path('planned-to-watch', views.planned_to_watch, name='planned_to_watch'),
    path('library/<slug:library_type>', views.library, name='library'),

    # STUFF RELATED TO INDIVIDUAL VIDEOS
    path('video/<slug:video_id>', views.view_video, name='video'),
    path('video/<slug:video_id>/mark/favorite', views.mark_video_favortie, name='mark_video_favorite'),
    path(
        'video/<slug:video_id>/mark/planned-to-watch',
        views.mark_video_planned_to_watch,
        name='mark_video_planned_to_watch'
    ),
    path('video/<slug:video_id>/notes', views.video_notes, name='video_notes'),
    path(
        'video/<slug:video_id>/get-video-completion-times',
        views.video_completion_times,
        name='video_completion_times'
    ),
    path('video/<slug:video_id>/add-user-label', views.add_video_user_label, name='add_video_user_label'),

    # STUFF RELATED TO VIDEO(S) INSIDE PLAYLISTS

    # STUFF RELATED TO ONE PLAYLIST
    path('playlist/<slug:playlist_id>', views.view_playlist, name='playlist'),
    path('playlist/<slug:playlist_id>/add-user-label', views.add_playlist_user_label, name='add_playlist_user_label'),
    path(
        'playlist/<slug:playlist_id>/<slug:video_id>/mark/watched',
        views.mark_video_watched,
        name='mark_video_watched'
    ),
    path('playlist/<slug:playlist_id>/settings', views.view_playlist_settings, name='view_playlist_settings'),
    path('playlist/<slug:playlist_id>/order-by/<slug:order_by>', views.order_playlist_by, name='order_playlist_by'),
    path('playlist/<slug:playlist_id>/mark-as/<slug:mark_as>', views.mark_playlist_as, name='mark_playlist_as'),
    path('playlist/<slug:playlist_id>/update/<slug:command>', views.update_playlist, name='update_playlist'),
    path(
        'playlist/<slug:playlist_id>/update-settings', views.update_playlist_settings, name='update_playlist_settings'
    ),
    path(
        'playlist/<slug:playlist_id>/<slug:order_by>/load-more-videos/<int:page>',
        views.load_more_videos,
        name='load_more_videos'
    ),
    path('playlist/<slug:playlist_id>/create-tag', views.create_playlist_tag, name='create_playlist_tag'),
    path('playlist/<slug:playlist_id>/add-tag', views.add_playlist_tag, name='add_playlist_tag'),
    path(
        'playlist/<slug:playlist_id>/remove-tag/<str:tag_name>', views.remove_playlist_tag, name='remove_playlist_tag'
    ),
    path('playlist/<slug:playlist_id>/get-tags', views.get_playlist_tags, name='get_playlist_tags'),
    path(
        'playlist/<slug:playlist_id>/get-unused-tags', views.get_unused_playlist_tags, name='get_unused_playlist_tags'
    ),
    path('playlist/<slug:playlist_id>/get-watch-message', views.get_watch_message, name='get_watch_message'),
    path(
        'playlist/<slug:playlist_id>/delete-videos/<slug:command>', views.playlist_delete_videos, name='delete_videos'
    ),
    path(
        'playlist/<slug:playlist_id>/delete-specific-videos/<slug:command>',
        views.delete_specific_videos,
        name='delete_specific_videos'
    ),
    path('playlist/<slug:playlist_id>/delete-playlist', views.delete_playlist, name='delete_playlist'),
    path('playlist/<slug:playlist_id>/reset-watched', views.reset_watched, name='reset_watched'),
    path(
        'playlist/<slug:playlist_id>/move-copy-videos/<str:action>',
        views.playlist_move_copy_videos,
        name='playlist_move_copy_videos'
    ),
    path(
        'playlist/<slug:playlist_id>/open-random-video',
        views.playlist_open_random_video,
        name='playlist_open_random_video'
    ),
    path(
        'playlist/<slug:playlist_id>/get-playlist-completion-times',
        views.playlist_completion_times,
        name='playlist_completion_times'
    ),
    path('playlist/<slug:playlist_id>/add-new-videos', views.playlist_add_new_videos, name='playlist_add_new_videos'),
    path(
        'playlist/<slug:playlist_id>/create-new-playlist',
        views.playlist_create_new_playlist,
        name='playlist_create_new_playlist'
    ),

    # STUFF RELATED TO PLAYLISTS IN BULK
    path(
        'playlists/<slug:playlist_type>/order-by/<slug:order_by>', views.order_playlists_by, name='order_playlists_by'
    ),
    path('playlists/tag/<str:tag>', views.tagged_playlists, name='tagged_playlists'),
    path('playlists/tag/<str:tag>/edit', views.edit_tag, name='edit_tag'),
    path('playlists/tag/<str:tag>/delete', views.delete_tag, name='delete_tag'),
]
