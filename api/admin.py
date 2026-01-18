from django.contrib import admin
from .models import NatureReserve


@admin.register(NatureReserve)
class NatureReserveAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "area_type", "created_at"]
    list_filter = ["area_type", "created_at"]
    search_fields = ["id", "name"]
    readonly_fields = ["created_at", "updated_at", "osm_data", "tags"]
    fields = ["id", "name", "area_type", "tags", "osm_data", "created_at", "updated_at"]
