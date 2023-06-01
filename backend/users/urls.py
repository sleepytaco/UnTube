from django.urls import path

from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('like-untube/', views.like_untube, name='like_untube'),
    path('unlike-untube/', views.unlike_untube, name='unlike_untube'),
    path('profile/', views.profile, name='profile'),
    path('about/', views.about, name='about'),
    path('logout/', views.log_out, name='log_out'),
    path('update/settings', views.update_settings, name='update_settings'),
    path('delete/account', views.delete_account, name='delete_account'),
    path('settings/', views.user_settings, name='settings'),
    path('import/liked-videos-playlist', views.get_user_liked_videos_playlist, name='get_user_liked_videos_playlist'),
    path('import/init', views.import_user_yt_playlists, name='import_user_yt_playlists'),
    path('import/start', views.start_import, name='start'),
    path('import/continue', views.continue_import, name='continue'),
    path('import/cancel', views.cancel_import, name='cancel'),
    path('updates/user-playlists/<slug:action>', views.user_playlists_updates, name='user_playlists_updates'),
]
