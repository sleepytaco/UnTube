from django.conf.urls import include
from django.urls import path
from . import views

urlpatterns = [
    path("", views.index, name='index'),
    path("profile/", views.profile, name='profile'),
    path("logout/", views.log_out, name='log_out'),
    path("update/settings", views.update_settings, name='update_settings'),
    path('accounts/', include('allauth.urls')),
    path("delete/account", views.delete_account, name='delete_account'),
    path('settings/', views.settings, name="settings"),

    path("import/start", views.start_import, name='start'),
    path("import/continue", views.continue_import, name='continue'),

    path("updates/user-playlists/<slug:action>", views.user_playlists_updates, name='user_playlists_updates'),
]
