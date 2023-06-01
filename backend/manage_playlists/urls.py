from django.urls import path

from . import views

urlpatterns = [
    # STUFF RELATED TO MANAGING A PLAYLIST
    path('', views.manage_playlists, name='manage_playlists'),
    path('save/<slug:what>', views.manage_save,
         name='manage_save'),  # to help auto save the input texts found in the below pages
    path('view/<slug:page>', views.manage_view_page,
         name='manage_view_page'),  # views the import pl, create pl, create untube pl pages
    path('import', views.manage_import_playlists, name='manage_import_playlists'),
    path('create', views.manage_create_playlist, name='manage_create_playlist'),
    path('nuke', views.manage_nuke_playlists, name='manage_nuke_playlists'),
]
