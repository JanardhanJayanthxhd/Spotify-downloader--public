from django.urls import path
from . import views

urlpatterns = [
    path('home/', views.home, name='home'),
    path('youtube/', views.youtube, name='youtube'),
    path('spotify/', views.spotify, name='spotify'),
    path('spotify/track', views.spotify_track, name='spotify track'),
    path('spotify/album', views.spotify_album, name='spotify album'),
    path('info/', views.info_page, name='info'),
]