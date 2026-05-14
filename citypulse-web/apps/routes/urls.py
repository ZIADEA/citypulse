from django.urls import path

from . import views

urlpatterns = [
    path("", views.home_redirect, name="home"),
    path("driver/", views.driver_dashboard, name="driver-dashboard"),
    path("driver/route/<int:route_id>/", views.driver_route_detail, name="driver-route-detail"),
    path("driver/history/", views.driver_history, name="driver-history"),
    path("client/", views.client_dashboard, name="client-dashboard"),
]
