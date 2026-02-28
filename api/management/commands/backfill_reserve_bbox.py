from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from api.geometry_utils import bbox_from_osm_element
from api.management.commands.export_geojson import REGION_BBOXES, parse_bbox
from api.models import NatureReserve

FALLBACK_BBOX = (0.0, 0.0, 0.0, 0.0)


class Command(BaseCommand):
    help = "Set min_lat, max_lat, min_lon, max_lon for reserves missing any bbox value."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Only report what would be updated, do not save.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Recompute bbox for all reserves, not only those with missing bbox.",
        )
        regions = ", ".join(REGION_BBOXES.keys())
        parser.add_argument(
            "--bbox",
            type=str,
            default=None,
            help=(
                f"Limit to reserves within bounding box. Either a region name ({regions}) "
                "or coordinates as min_lon,min_lat,max_lon,max_lat"
            ),
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        force = options["force"]
        bbox_str = options.get("bbox")

        bbox = None
        if bbox_str:
            bbox = parse_bbox(bbox_str)
            if bbox is None:
                raise CommandError(
                    f"Invalid bbox: {bbox_str}. Use a region name or "
                    "min_lon,min_lat,max_lon,max_lat"
                )
            self.stdout.write(f"Using bounding box: {bbox}")

        if force:
            reserves = NatureReserve.objects.all()
        else:
            reserves = NatureReserve.objects.filter(
                Q(min_lat__isnull=True)
                | Q(max_lat__isnull=True)
                | Q(min_lon__isnull=True)
                | Q(max_lon__isnull=True)
            )

        if bbox:
            min_lon, min_lat, max_lon, max_lat = bbox
            reserves = reserves.filter(
                min_lon__lte=max_lon,
                max_lon__gte=min_lon,
                min_lat__lte=max_lat,
                max_lat__gte=min_lat,
            )

        total = reserves.count()
        if total == 0:
            if force:
                self.stdout.write("No reserves in database.")
            else:
                self.stdout.write("No reserves with missing bbox.")
            return

        if force:
            self.stdout.write(f"Processing all {total} reserve(s).")
        else:
            self.stdout.write(f"Found {total} reserve(s) with missing bbox.")
        if dry_run:
            self.stdout.write("Dry run: no changes written.")
        updated = 0
        fallback_count = 0
        for reserve in reserves:
            reserve_bbox = bbox_from_osm_element(reserve.osm_data or {})
            if reserve_bbox is None:
                reserve_bbox = FALLBACK_BBOX
                fallback_count += 1
                self.stdout.write(
                    self.style.WARNING(
                        f"  {reserve.id}: no bbox from osm_data, using fallback"
                    )
                )
            if not dry_run:
                reserve.min_lon, reserve.min_lat, reserve.max_lon, reserve.max_lat = (
                    reserve_bbox
                )
                reserve.save(update_fields=["min_lon", "min_lat", "max_lon", "max_lat"])
            updated += 1
        msg = f"Processed {updated} reserve(s)"
        if fallback_count:
            msg += f", {fallback_count} with fallback bbox"
        msg += "."
        self.stdout.write(msg)
