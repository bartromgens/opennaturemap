import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from api.geometry_utils import geojson_geometry_area, reserve_geojson_features
from api.models import NatureReserve


class Command(BaseCommand):
    help = "Export NatureReserves to GeoJSON (from stored geojson or osm_data)"

    def add_arguments(self, parser):
        default_out = settings.BASE_DIR / "data" / "nature_reserves.geojson"
        parser.add_argument(
            "--output",
            type=str,
            default=str(default_out),
            help="Output file path (default: data/nature_reserves.geojson)",
        )

    def handle(self, *args, **options):
        output_path = Path(options["output"])

        self.stdout.write("Gathering all NatureReserves...")
        reserves = NatureReserve.objects.all()
        total_count = reserves.count()

        if total_count == 0:
            self.stdout.write(
                self.style.WARNING("No nature reserves found in database")
            )
            return

        self.stdout.write(f"Found {total_count} nature reserves")
        self.stdout.write("Building GeoJSON features from reserves...")

        all_features = []
        processed_count = 0
        error_count = 0

        for reserve in reserves:
            try:
                if reserve.geojson:
                    features = reserve.geojson
                else:
                    operator_ids = list(reserve.operators.values_list("id", flat=True))
                    features = reserve_geojson_features(
                        reserve.osm_data or {},
                        reserve.id,
                        reserve.name,
                        reserve.area_type,
                        operator_ids,
                        reserve.tags or {},
                        reserve.protect_class,
                    )
                all_features.extend(features)
                processed_count += 1

                if processed_count % 100 == 0:
                    msg = f"  Processed {processed_count}/{total_count} " "reserves..."
                    self.stdout.write(msg)

            except Exception as e:
                err_msg = f"  Error processing reserve {reserve.id}: {e}"
                self.stdout.write(self.style.ERROR(err_msg))
                error_count += 1
                continue

        if not all_features:
            self.stdout.write(self.style.WARNING("No features generated from reserves"))
            return

        def feature_area(f: dict) -> float:
            geom = f.get("geometry")
            return geojson_geometry_area(geom) if isinstance(geom, dict) else 0.0

        all_features.sort(key=feature_area)

        geojson_collection = {
            "type": "FeatureCollection",
            "features": all_features,
        }

        self.stdout.write(f"Writing {len(all_features)} features to {output_path}...")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(geojson_collection, f, indent=2, ensure_ascii=False)

        self.stdout.write(self.style.SUCCESS("\nExport complete:"))
        self.stdout.write(f"  Processed: {processed_count}")
        self.stdout.write(f"  Features: {len(all_features)}")
        self.stdout.write(f"  Errors: {error_count}")
        self.stdout.write(f"  Output: {output_path.absolute()}")
