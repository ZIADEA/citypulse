from django.conf import settings
from django.db import models


class DriverRoute(models.Model):
    vehicle_id_ext = models.CharField(max_length=64)
    driver_id_ext = models.CharField(max_length=64)
    planned_date = models.DateField()
    stops_json = models.JSONField(default=list)
    driver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="driver_routes",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Route {self.id} - {self.planned_date}"
