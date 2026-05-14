from django.urls import path

from . import views

urlpatterns = [
    path("sync/clients/", views.sync_clients, name="sync-clients"),
    path("sync/routes/", views.sync_routes, name="sync-routes"),
    path("deliveries/confirmations/", views.deliveries_confirmations, name="deliveries-confirmations"),
    path("deliveries/proofs/", views.deliveries_proofs, name="deliveries-proofs"),
    path("deliveries/confirm/", views.delivery_confirm, name="deliveries-confirm"),
    path("users/create/", views.create_web_user, name="users-create"),
]
