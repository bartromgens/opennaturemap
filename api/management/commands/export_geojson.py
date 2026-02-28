import json
import sqlite3
import tempfile
from pathlib import Path
from typing import Optional, Tuple

from django.conf import settings
from django.core.management.base import BaseCommand

from api.geometry_utils import geojson_geometry_area, reserve_geojson_features
from api.models import NatureReserve

BATCH_SIZE = 10000

REGION_BBOXES: dict[str, Tuple[float, float, float, float]] = {
    "world": (-180, -85, 180, 85),
    "europe": (-25, 34, 45, 72),
    "netherlands": (3.2, 50.75, 7.2, 53.7),
    "spain": (-9.3, 36.0, 4.3, 43.8),
    "france": (-5.5, 41.3, 9.6, 51.1),
    "switzerland": (5.9, 45.8, 10.5, 47.8),
    "germany": (5.9, 47.3, 15.0, 55.1),
    "belgium": (2.5, 49.5, 6.4, 51.5),
    "italy": (6.6, 36.6, 18.5, 47.1),
    "norway": (4.6, 57.9, 31.1, 71.2),
}


def parse_bbox(
    bbox_str: Optional[str],
) -> Optional[Tuple[float, float, float, float]]:
    if not bbox_str:
        return None

    lower = bbox_str.lower().strip()
    if lower in REGION_BBOXES:
        return REGION_BBOXES[lower]

    try:
        coords = [float(x) for x in bbox_str.split(",")]
        if len(coords) == 4:
            return (coords[0], coords[1], coords[2], coords[3])
    except ValueError:
        pass

    return None


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
        regions = ", ".join(REGION_BBOXES.keys())
        parser.add_argument(
            "--bbox",
            type=str,
            default=None,
            help=(
                f"Bounding box filter. Either a region name ({regions}) "
                "or coordinates as min_lon,min_lat,max_lon,max_lat"
            ),
        )

    def handle(self, *args, **options):
        output_path = Path(options["output"])
        bbox_str = options.get("bbox")
        bbox = parse_bbox(bbox_str)

        if bbox_str and bbox is None:
            self.stdout.write(
                self.style.ERROR(
                    f"Invalid bbox: {bbox_str}. Use a region name or "
                    "min_lon,min_lat,max_lon,max_lat"
                )
            )
            return

        queryset = NatureReserve.objects.all()
        if bbox:
            min_lon, min_lat, max_lon, max_lat = bbox
            queryset = queryset.filter(
                min_lon__lte=max_lon,
                max_lon__gte=min_lon,
                min_lat__lte=max_lat,
                max_lat__gte=min_lat,
            )
            self.stdout.write(f"Filtering to bbox: {bbox}")

        self.stdout.write("Counting NatureReserves...")
        total_count = queryset.count()

        if total_count == 0:
            self.stdout.write(
                self.style.WARNING("No nature reserves found in database")
            )
            return

        self.stdout.write(f"Found {total_count} nature reserves")
        self.stdout.write("Processing reserves and storing features temporarily...")

        with tempfile.NamedTemporaryFile(suffix=".db", delete=True) as tmp:
            tmp_db_path = tmp.name
            self._export_with_temp_db(tmp_db_path, output_path, total_count, queryset)

    def _export_with_temp_db(
        self, tmp_db_path: str, output_path: Path, total_count: int, queryset
    ) -> None:
        conn = sqlite3.connect(tmp_db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE features (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                area REAL,
                geojson TEXT
            )
        """)
        conn.commit()

        processed_count = 0
        error_count = 0
        feature_count = 0

        reserves = queryset.only(
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
                    if "id" in feature and not isinstance(feature["id"], (int, float)):
                        feature = {k: v for k, v in feature.items() if k != "id"}
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
