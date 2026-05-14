from django.contrib import admin

from .models import DeliveryProof, DeliveryTracking


@admin.register(DeliveryTracking)
class DeliveryTrackingAdmin(admin.ModelAdmin):
    list_display = ("order_ref", "status", "eta", "last_update")


@admin.register(DeliveryProof)
class DeliveryProofAdmin(admin.ModelAdmin):
    list_display = ("order_id_ext", "confirmed_at")
