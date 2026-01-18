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

    @property
    def bounds(self) -> dict | None:
        return self.osm_data.get("bounds")

    @property
    def geometry(self) -> list | None:
        return self.osm_data.get("geometry")

    @property
    def operator(self) -> str | None:
        tags = self.osm_data.get("tags", {})
        return tags.get("operator")

    @property
    def website(self) -> str | None:
        tags = self.osm_data.get("tags", {})
        return tags.get("website")

    @property
    def wikidata(self) -> str | None:
        tags = self.osm_data.get("tags", {})
        return tags.get("wikidata")

    @property
    def wikipedia(self) -> str | None:
        tags = self.osm_data.get("tags", {})
        return tags.get("wikipedia")
