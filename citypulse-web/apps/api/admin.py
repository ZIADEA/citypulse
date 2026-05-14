from django.contrib import admin

from .models import SyncLog


@admin.register(SyncLog)
class SyncLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "direction", "type", "records_count", "status")
