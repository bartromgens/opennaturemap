import json
from pathlib import Path
from django.core.management.base import BaseCommand
from django.conf import settings
from api.models import NatureReserve
import osm2geojson


class Command(BaseCommand):
    help = "Export all NatureReserves to a single GeoJSON file using osm2geojson"

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            type=str,
            default=str(settings.BASE_DIR / "data" / "nature_reserves.geojson"),
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
        self.stdout.write("Converting to GeoJSON using osm2geojson...")

        all_features = []
        processed_count = 0
        error_count = 0

        for reserve in reserves:
            try:
                osm_element = reserve.osm_data

                osm_response = {"elements": [osm_element]}
                geojson_result = osm2geojson.json2geojson(osm_response)

                if isinstance(geojson_result, dict) and "features" in geojson_result:
                    features = geojson_result["features"]
                elif isinstance(geojson_result, list):
                    features = geojson_result
                else:
                    features = []

                for feature in features:
                    if (
                        not isinstance(feature, dict)
                        or feature.get("type") != "Feature"
                    ):
                        continue

                    feature["id"] = reserve.id
                    if "properties" not in feature:
                        feature["properties"] = {}

                    feature["properties"]["id"] = reserve.id
                    osm_type = (
                        reserve.osm_data.get("type")
                        if isinstance(reserve.osm_data, dict)
                        else None
                    ) or reserve.id.split("_")[0]
                    feature["properties"]["osm_type"] = osm_type
                    feature["properties"]["name"] = reserve.name
                    feature["properties"]["area_type"] = reserve.area_type
                    ids = list(reserve.operators.values_list("id", flat=True))
                    feature["properties"]["operator_ids"] = ",".join(str(i) for i in ids)
                    feature["properties"].update(reserve.tags)

                    all_features.append(feature)

                processed_count += 1

                if processed_count % 100 == 0:
                    self.stdout.write(
                        f"  Processed {processed_count}/{total_count} reserves..."
                    )

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"  Error processing reserve {reserve.id}: {e}")
                )
                error_count += 1
                continue

        if not all_features:
            self.stdout.write(self.style.WARNING("No features generated from reserves"))
            return

        geojson_collection = {"type": "FeatureCollection", "features": all_features}

        self.stdout.write(f"Writing {len(all_features)} features to {output_path}...")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(geojson_collection, f, indent=2, ensure_ascii=False)

        self.stdout.write(self.style.SUCCESS(f"\nExport complete:"))
        self.stdout.write(f"  Processed: {processed_count}")
        self.stdout.write(f"  Features: {len(all_features)}")
        self.stdout.write(f"  Errors: {error_count}")
        self.stdout.write(f"  Output: {output_path.absolute()}")
