from django.contrib import admin
from .models import ImportGrid, NatureReserve, Operator


@admin.register(ImportGrid)
class ImportGridAdmin(admin.ModelAdmin):
    list_display = [
        "grid_number",
        "min_lon",
        "min_lat",
        "max_lon",
        "max_lat",
        "last_updated",
        "reserves_created_count",
        "reserves_updated_count",
        "success",
    ]
    list_filter = ["success", "last_updated"]
    search_fields = ["error_message"]
    readonly_fields = [
        "grid_number",
        "min_lon",
        "min_lat",
        "max_lon",
        "max_lat",
        "last_updated",
        "reserves_created_count",
        "reserves_updated_count",
        "success",
        "error_message",
    ]
    ordering = ["-last_updated"]


@admin.register(Operator)
class OperatorAdmin(admin.ModelAdmin):
    list_display = ["name"]
    search_fields = ["name"]


def operators_display(obj: NatureReserve) -> str:
    return ", ".join(op.name for op in obj.operators.all())


operators_display.short_description = "Operators"


@admin.register(NatureReserve)
class NatureReserveAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "name",
        operators_display,
        "area_type",
        "protect_class",
        "min_lat",
        "max_lat",
        "min_lon",
        "max_lon",
        "created_at",
        "updated_at",
    ]
    list_filter = ["area_type", "protect_class", "operators", "created_at"]
    search_fields = ["id", "name"]
    readonly_fields = ["created_at", "updated_at", "osm_data", "tags"]
    filter_horizontal = ["operators"]
    fields = [
        "id",
        "name",
        "operators",
        "area_type",
        "protect_class",
        "tags",
        "osm_data",
        "created_at",
        "updated_at",
    ]
