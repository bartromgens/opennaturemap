import json
import sqlite3
import tempfile
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from api.geometry_utils import geojson_geometry_area, reserve_geojson_features
from api.models import NatureReserve

BATCH_SIZE = 10000


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

        self.stdout.write("Counting NatureReserves...")
        total_count = NatureReserve.objects.count()

        if total_count == 0:
            self.stdout.write(
                self.style.WARNING("No nature reserves found in database")
            )
            return

        self.stdout.write(f"Found {total_count} nature reserves")
        self.stdout.write("Processing reserves and storing features temporarily...")

        with tempfile.NamedTemporaryFile(suffix=".db", delete=True) as tmp:
            tmp_db_path = tmp.name
            self._export_with_temp_db(tmp_db_path, output_path, total_count)

    def _export_with_temp_db(
        self, tmp_db_path: str, output_path: Path, total_count: int
    ) -> None:
        conn = sqlite3.connect(tmp_db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE features (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                area REAL,
                geojson TEXT
            )
        """
        )
        conn.commit()

        processed_count = 0
        error_count = 0
        feature_count = 0

        reserves = NatureReserve.objects.only(
            "id", "name", "area_type", "tags", "protect_class", "geojson", "osm_data"
        ).iterator(chunk_size=BATCH_SIZE)

        batch = []
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

                for feature in features:
                    geom = feature.get("geometry")
                    area = (
                        geojson_geometry_area(geom) if isinstance(geom, dict) else 0.0
                    )
                    batch.append((area, json.dumps(feature, ensure_ascii=False)))
                    feature_count += 1

                if len(batch) >= BATCH_SIZE:
                    cursor.executemany(
                        "INSERT INTO features (area, geojson) VALUES (?, ?)", batch
                    )
                    conn.commit()
                    batch = []

                processed_count += 1
                if processed_count % 10000 == 0:
                    msg = f"  Processed {processed_count}/{total_count} reserves..."
                    self.stdout.write(msg)

            except Exception as e:
                err_msg = f"  Error processing reserve {reserve.id}: {e}"
                self.stdout.write(self.style.ERROR(err_msg))
                error_count += 1
                continue

        if batch:
            cursor.executemany(
                "INSERT INTO features (area, geojson) VALUES (?, ?)", batch
            )
            conn.commit()

        if feature_count == 0:
            conn.close()
            self.stdout.write(self.style.WARNING("No features generated from reserves"))
            return

        self.stdout.write(f"Writing {feature_count} features to {output_path}...")
        output_path.parent.mkdir(parents=True, exist_ok=True)

        cursor.execute("CREATE INDEX idx_area ON features (area)")
        conn.commit()

        with open(output_path, "w", encoding="utf-8") as f:
            f.write('{\n  "type": "FeatureCollection",\n  "features": [\n')

            cursor.execute("SELECT geojson FROM features ORDER BY area")
            first = True
            while True:
                rows = cursor.fetchmany(BATCH_SIZE)
                if not rows:
                    break
                for (geojson_str,) in rows:
                    if not first:
                        f.write(",\n")
                    first = False
                    f.write("    ")
                    f.write(geojson_str)

            f.write("\n  ]\n}\n")

        conn.close()

        self.stdout.write(self.style.SUCCESS("\nExport complete:"))
        self.stdout.write(f"  Processed: {processed_count}")
        self.stdout.write(f"  Features: {feature_count}")
        self.stdout.write(f"  Errors: {error_count}")
        self.stdout.write(f"  Output: {output_path.absolute()}")
