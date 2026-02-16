from django.db import models


class Operator(models.Model):
    name = models.CharField(max_length=255, unique=True)

    class Meta:
        db_table = "operators"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class ImportGrid(models.Model):
    grid_number = models.PositiveIntegerField(
        help_text=(
            "1-based tile index from the run that last processed this grid. "
            "Depends on the bbox used in that run; resume uses bbox "
            "coordinates only."
        )
    )
    min_lon = models.FloatField()
    min_lat = models.FloatField()
    max_lon = models.FloatField()
    max_lat = models.FloatField()
    last_updated = models.DateTimeField(null=True, blank=True)
    reserves_created_count = models.PositiveIntegerField(default=0)
    reserves_updated_count = models.PositiveIntegerField(default=0)
    success = models.BooleanField(default=False)
    error_message = models.TextField(null=True, blank=True)

    class Meta:
        db_table = "import_grids"
        constraints = [
            models.UniqueConstraint(
                fields=["min_lon", "min_lat", "max_lon", "max_lat"],
                name="import_grid_bbox_unique",
            )
        ]
        indexes = [
            models.Index(fields=["success"]),
            models.Index(fields=["last_updated"]),
        ]
        ordering = ["grid_number"]

    def __str__(self) -> str:
        return (
            f"Grid {self.grid_number} "
            f"({self.min_lon},{self.min_lat},{self.max_lon},{self.max_lat})"
        )

    @property
    def bbox(self) -> tuple[float, float, float, float]:
        return (self.min_lon, self.min_lat, self.max_lon, self.max_lat)


class NatureReserve(models.Model):
    id = models.CharField(max_length=255, primary_key=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    operators = models.ManyToManyField(
        Operator,
        related_name="nature_reserves",
        blank=True,
    )
    osm_data = models.JSONField()
    geojson = models.JSONField(null=True, blank=True)
    tags = models.JSONField(default=dict)
    area_type = models.CharField(max_length=100)
    protect_class = models.CharField(max_length=100, null=True, blank=True)
    min_lat = models.FloatField(db_index=True)
    max_lat = models.FloatField(db_index=True)
    min_lon = models.FloatField(db_index=True)
    max_lon = models.FloatField(db_index=True)
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
