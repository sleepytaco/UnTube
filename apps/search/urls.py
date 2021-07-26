from django.urls import path
from . import views

urlpatterns = [
    path("", views.search, name="search"),
    path("untube/", views.search_UnTube, name="search_UnTube"),
    path("playlists/<slug:playlist_type>", views.search_playlists, name="search_playlists"),
    path("videos/<slug:playlist_type>", views.search_playlists, name="search_playlists"),
    path("tagged-playlists/<str:tag>", views.search_tagged_playlists, name="search_tagged_playlists"),
]
