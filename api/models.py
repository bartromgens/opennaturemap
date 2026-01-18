from django.db import models


class NatureReserve(models.Model):
    id = models.CharField(max_length=255, primary_key=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    osm_data = models.JSONField()
    tags = models.JSONField(default=dict)
    area_type = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "nature_reserves"
        indexes = [
            models.Index(fields=["area_type"]),
            models.Index(fields=["name"]),
        ]

    def __str__(self) -> str:
        return self.name or self.id
