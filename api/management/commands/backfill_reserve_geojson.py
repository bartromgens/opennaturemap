from django.core.management.base import BaseCommand
from django.db.models import Q

from api.geometry_utils import reserve_geojson_features
from api.models import NatureReserve


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
            reserves = NatureReserve.objects.filter(Q(geojson__isnull=True))
            total = reserves.count()
            if total == 0:
                self.stdout.write("No reserves with missing geojson.")
                return
            self.stdout.write(f"Found {total} reserve(s) with missing geojson.")
        if dry_run:
            self.stdout.write("Dry run: no changes written.")
        updated = 0
        no_geometry = 0
        for i, reserve in enumerate(reserves.iterator(), start=1):
            operator_ids = list(reserve.operators.values_list("id", flat=True))
            geojson_list = reserve_geojson_features(
                reserve.osm_data or {},
                reserve.id,
                reserve.name,
                reserve.area_type,
                operator_ids,
                reserve.tags or {},
                reserve.protect_class,
            )
            pct = i * 100 // total
            if not geojson_list:
                no_geometry += 1
                self.stdout.write(
                    self.style.WARNING(
                        f"[{pct:3d}%] {reserve.id}: no geometry from osm_data, skipping"
                    )
                )
                continue
            if not dry_run:
                reserve.geojson = geojson_list
                reserve.save(update_fields=["geojson"])
            updated += 1
            self.stdout.write(f"[{pct:3d}%] {reserve.id}: updated")
        msg = f"Processed {updated} reserve(s)"
        if no_geometry:
            msg += f", {no_geometry} with no geometry (skipped)"
        msg += "."
        self.stdout.write(msg)
