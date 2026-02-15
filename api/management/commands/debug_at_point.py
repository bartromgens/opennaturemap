from django.core.management.base import BaseCommand

from api.geometry_utils import (
    geometry_from_osm_element,
    point_in_geojson_geometry,
)
from api.models import NatureReserve


class Command(BaseCommand):
    help = "Debug at_point: show bbox stats and optionally scan reserves for point-in-geometry"

    def add_arguments(self, parser):
        parser.add_argument("lat", type=float, help="Latitude")
        parser.add_argument("lon", type=float, help="Longitude")
        parser.add_argument(
            "--scan",
            type=int,
            default=0,
            metavar="N",
            help=(
                "Scan up to N reserves (with bbox) for point-in-geometry; 0 = only "
                "bbox stats. Use a large N (e.g. 10000) to find reserves containing "
                "the point when bbox_near=0."
            ),
        )

    def handle(self, *args, **options):
        lat = options["lat"]
        lon = options["lon"]
        scan_n = options["scan"]

        total = NatureReserve.objects.count()
        with_bbox = NatureReserve.objects.filter(
            min_lat__isnull=False,
            max_lat__isnull=False,
            min_lon__isnull=False,
            max_lon__isnull=False,
        ).count()
        bbox_contains = NatureReserve.objects.filter(
            min_lat__isnull=False,
            max_lat__isnull=False,
            min_lon__isnull=False,
            max_lon__isnull=False,
            min_lat__lte=lat,
            max_lat__gte=lat,
            min_lon__lte=lon,
            max_lon__gte=lon,
        ).count()
        eps = 0.01
        bbox_near = NatureReserve.objects.filter(
            min_lat__isnull=False,
            max_lat__isnull=False,
            min_lon__isnull=False,
            max_lon__isnull=False,
            min_lat__lte=lat + eps,
            max_lat__gte=lat - eps,
            min_lon__lte=lon + eps,
            max_lon__gte=lon - eps,
        ).count()

        self.stdout.write(f"Point: lat={lat} lon={lon}")
        self.stdout.write(f"Total reserves: {total}")
        self.stdout.write(f"With non-null bbox: {with_bbox}")
        self.stdout.write(f"Bbox contains point: {bbox_contains}")
        self.stdout.write(f"Bbox near point (±{eps}): {bbox_near}")

        if scan_n > 0:
            self.stdout.write("")
            qs = NatureReserve.objects.only(
                "id", "name", "osm_data", "min_lat", "max_lat", "min_lon", "max_lon"
            )[:scan_n]
            containing = []
            no_geom = 0
            for reserve in qs:
                geom = geometry_from_osm_element(reserve.osm_data)
                if geom is None:
                    no_geom += 1
                    continue
                if point_in_geojson_geometry(lon, lat, geom):
                    containing.append(reserve)
            self.stdout.write(f"Scanned first {min(scan_n, total)} reserves:")
            self.stdout.write(f"  no_geom={no_geom}, containing point={len(containing)}")
            for r in containing:
                self.stdout.write(
                    f"  {r.id} {r.name or '(no name)'} "
                    f"bbox=({r.min_lon},{r.min_lat},{r.max_lon},{r.max_lat})"
                )
