from django.db import models


class SyncLog(models.Model):
    direction = models.CharField(max_length=10)
    type = models.CharField(max_length=50)
    records_count = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=20)
    error_msg = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.direction}:{self.type}:{self.status}"
