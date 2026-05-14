from django.urls import path

from . import views

urlpatterns = [
    path("driver/login/", views.driver_login, name="driver-login"),
    path("client/login/", views.client_login, name="client-login"),
    path("logout/", views.do_logout, name="logout"),
]
