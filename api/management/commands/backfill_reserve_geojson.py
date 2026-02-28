from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q

from api.geometry_utils import reserve_geojson_features
from api.management.commands.export_geojson import REGION_BBOXES, parse_bbox
from api.models import NatureReserve

BATCH_SIZE = 1000


class Command(BaseCommand):
    help = "Populate geojson field for reserves from osm_data (missing or all with --force)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Only report what would be updated, do not save.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Recompute geojson for all reserves, not only those with null geojson.",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=BATCH_SIZE,
            help=f"Number of reserves to update per batch (default: {BATCH_SIZE}).",
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
        batch_size = options["batch_size"]
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
            qs = NatureReserve.objects.all()
        else:
            qs = NatureReserve.objects.filter(Q(geojson__isnull=True))

        if bbox:
            min_lon, min_lat, max_lon, max_lat = bbox
            qs = qs.filter(
                min_lon__lte=max_lon,
                max_lon__gte=min_lon,
                min_lat__lte=max_lat,
                max_lat__gte=min_lat,
            )

        total = qs.count()
        if total == 0:
            if force:
                self.stdout.write("No reserves in database.")
            else:
                self.stdout.write("No reserves with missing geojson.")
            return

        if force:
            self.stdout.write(f"Processing all {total} reserve(s).")
        else:
            self.stdout.write(f"Found {total} reserve(s) with missing geojson.")

        if dry_run:
            self.stdout.write("Dry run: no changes written.")

        updated = 0
        no_geometry = 0
        batch_to_update: list[NatureReserve] = []
        processed = 0

        reserves = qs.prefetch_related("operators").iterator(chunk_size=batch_size)

        for reserve in reserves:
            processed += 1
            operator_ids = [op.id for op in reserve.operators.all()]
            geojson_list = reserve_geojson_features(
                reserve.osm_data or {},
                reserve.id,
                reserve.name,
                reserve.area_type,
                operator_ids,
                reserve.tags or {},
                reserve.protect_class,
            )

            if not geojson_list:
                no_geometry += 1
                continue

            reserve.geojson = geojson_list
            batch_to_update.append(reserve)
            updated += 1

            if len(batch_to_update) >= batch_size:
                if not dry_run:
                    self._bulk_update(batch_to_update)
                pct = processed * 100 // total
                self.stdout.write(f"[{pct:3d}%] Updated {updated} reserves...")
                batch_to_update = []

        if batch_to_update and not dry_run:
            self._bulk_update(batch_to_update)

        msg = f"Processed {updated} reserve(s)"
        if no_geometry:
            msg += f", {no_geometry} with no geometry (skipped)"
        msg += "."
        self.stdout.write(msg)

    def _bulk_update(self, reserves: list[NatureReserve]) -> None:
        with transaction.atomic():
            NatureReserve.objects.bulk_update(reserves, ["geojson"], batch_size=500)
