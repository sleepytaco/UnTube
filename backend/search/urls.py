from django.urls import path

from . import views

urlpatterns = [
    path('', views.search, name='search'),
    path('untube/', views.search_UnTube, name='search_UnTube'),
    path('library/<slug:library_type>', views.search_library, name='search_library'),
    path('tagged-playlists/<str:tag>', views.search_tagged_playlists, name='search_tagged_playlists'),
]
