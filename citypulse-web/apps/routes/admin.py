from django.contrib import admin

from .models import DriverRoute


@admin.register(DriverRoute)
class DriverRouteAdmin(admin.ModelAdmin):
    list_display = ("id", "vehicle_id_ext", "driver_id_ext", "planned_date")
