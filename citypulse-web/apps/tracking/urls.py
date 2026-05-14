from django.urls import path

from . import views

urlpatterns = [
    path("client/track/<str:ref>/", views.client_track, name="client-track"),
    path("track/<str:ref>/", views.public_track, name="public-track"),
    path("driver/confirm-delivery/", views.confirm_delivery, name="driver-confirm-delivery"),
]
