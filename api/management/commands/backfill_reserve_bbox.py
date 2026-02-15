from django.core.management.base import BaseCommand
from django.db.models import Q

from api.geometry_utils import bbox_from_osm_element
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

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        force = options["force"]
        if force:
            reserves = NatureReserve.objects.all()
            total = reserves.count()
            if total == 0:
                self.stdout.write("No reserves in database.")
                return
            self.stdout.write(f"Processing all {total} reserve(s).")
        else:
            reserves = NatureReserve.objects.filter(
                Q(min_lat__isnull=True)
                | Q(max_lat__isnull=True)
                | Q(min_lon__isnull=True)
                | Q(max_lon__isnull=True)
            )
            total = reserves.count()
            if total == 0:
                self.stdout.write("No reserves with missing bbox.")
                return
            self.stdout.write(f"Found {total} reserve(s) with missing bbox.")
        if dry_run:
            self.stdout.write("Dry run: no changes written.")
        updated = 0
        fallback_count = 0
        for reserve in reserves:
            bbox = bbox_from_osm_element(reserve.osm_data or {})
            if bbox is None:
                bbox = FALLBACK_BBOX
                fallback_count += 1
                self.stdout.write(
                    self.style.WARNING(
                        f"  {reserve.id}: no bbox from osm_data, using fallback"
                    )
                )
            if not dry_run:
                reserve.min_lon, reserve.min_lat, reserve.max_lon, reserve.max_lat = (
                    bbox
                )
                reserve.save(update_fields=["min_lon", "min_lat", "max_lon", "max_lat"])
            updated += 1
        msg = f"Processed {updated} reserve(s)"
        if fallback_count:
            msg += f", {fallback_count} with fallback bbox"
        msg += "."
        self.stdout.write(msg)
