import shutil
import subprocess
import tempfile
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

from api.management.utils import find_executable


class Command(BaseCommand):
    help = "Convert a shapefile (e.g. from ProtectedPlanet/WDPA) to MBTiles via GeoJSON"

    def add_arguments(self, parser):
        parser.add_argument(
            "input",
            type=str,
            help="Path to the input shapefile (.shp)",
        )
        parser.add_argument(
            "--output",
            type=str,
            default=str(settings.BASE_DIR / "data" / "nature_reserves.mbtiles"),
            help="Output MBTiles file path (default: data/nature_reserves.mbtiles)",
        )
        parser.add_argument(
            "--geojson-output",
            type=str,
            default=None,
            help=(
                "Intermediate GeoJSON file path. "
                "If omitted a temporary file is used and deleted afterwards."
            ),
        )
        parser.add_argument(
            "--layer-name",
            type=str,
            default="nature_reserves",
            help="Layer name in MBTiles (default: nature_reserves)",
        )
        parser.add_argument(
            "--min-zoom",
            type=int,
            default=0,
            help="Minimum zoom level (default: 0)",
        )
        parser.add_argument(
            "--max-zoom",
            type=int,
            default=14,
            help="Maximum zoom level (default: 14)",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Overwrite output file if it exists",
        )
        parser.add_argument(
            "--maximum-tile-bytes",
            type=int,
            default=500_000,
            metavar="BYTES",
            help="Max size per tile in bytes passed to tippecanoe (default: 500000)",
        )
        parser.add_argument(
            "--low-detail",
            type=int,
            default=12,
            metavar="DETAIL",
            help="Low-detail level passed to tippecanoe (default: 12)",
        )
        parser.add_argument(
            "--minimum-detail",
            type=int,
            default=7,
            metavar="DETAIL",
            help="Minimum detail passed to tippecanoe (default: 7)",
        )

    def handle(self, *args, **options):
        input_path = Path(options["input"])
        output_path = options["output"]
        geojson_output = options["geojson_output"]
        layer_name = options["layer_name"]
        min_zoom = options["min_zoom"]
        max_zoom = options["max_zoom"]
        force = options["force"]
        maximum_tile_bytes = options["maximum_tile_bytes"]
        low_detail = options["low_detail"]
        minimum_detail = options["minimum_detail"]

        if not input_path.exists():
            raise CommandError(f"Input shapefile not found: {input_path}")

        if input_path.suffix.lower() != ".shp":
            raise CommandError(
                f"Expected a .shp file, got: {input_path.suffix}. "
                "Pass the .shp component of the shapefile bundle."
            )

        ogr2ogr_path = find_executable(
            "ogr2ogr",
            [
                "/usr/bin/ogr2ogr",
                "/usr/local/bin/ogr2ogr",
                "/opt/homebrew/bin/ogr2ogr",
            ],
            "ogr2ogr is not installed or not in PATH.\n"
            "Install GDAL tools:\n"
            "  Ubuntu/Debian: sudo apt-get install gdal-bin\n"
            "  macOS:         brew install gdal",
        )
        self._log_ogr2ogr_version(ogr2ogr_path)

        use_temp = geojson_output is None
        tmp_dir = None
        if use_temp:
            tmp_dir = tempfile.mkdtemp()
            geojson_path = Path(tmp_dir) / "converted.geojson"
        else:
            geojson_path = Path(geojson_output)

        try:
            self.stdout.write("=" * 60)
            self.stdout.write("Step 1: Converting shapefile to GeoJSON")
            self.stdout.write("=" * 60)
            self._convert_to_geojson(ogr2ogr_path, input_path, geojson_path)

            self.stdout.write("")
            self.stdout.write("=" * 60)
            self.stdout.write("Step 2: Converting GeoJSON to MBTiles")
            self.stdout.write("=" * 60)
            call_command(
                "geojson_to_mbtiles",
                input=str(geojson_path),
                output=output_path,
                layer_name=layer_name,
                min_zoom=min_zoom,
                max_zoom=max_zoom,
                force=force,
                maximum_tile_bytes=maximum_tile_bytes,
                low_detail=low_detail,
                minimum_detail=minimum_detail,
            )
        finally:
            if use_temp and tmp_dir:
                shutil.rmtree(tmp_dir, ignore_errors=True)

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("=" * 60))
        self.stdout.write(self.style.SUCCESS("Conversion complete!"))
        self.stdout.write(self.style.SUCCESS("=" * 60))
        self.stdout.write(f"MBTiles output: {Path(output_path).absolute()}")

    def _convert_to_geojson(
        self, ogr2ogr_path: str, input_path: Path, output_path: Path
    ) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)

        cmd = [
            ogr2ogr_path,
            "-f",
            "GeoJSON",
            "-t_srs",
            "EPSG:4326",
            str(output_path),
            str(input_path),
        ]

        self.stdout.write(f"Running: {' '.join(cmd)}")
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            if result.stdout:
                self.stdout.write(result.stdout)
            self.stdout.write(
                self.style.SUCCESS(f"GeoJSON written to {output_path.absolute()}")
            )
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr if e.stderr else str(e)
            raise CommandError(f"ogr2ogr failed: {error_msg}")

    def _log_ogr2ogr_version(self, ogr2ogr_path: str) -> None:
        try:
            result = subprocess.run(
                [ogr2ogr_path, "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            version = (result.stdout or result.stderr or "").strip()
            if version:
                self.stdout.write(f"Using ogr2ogr: {version}")
        except Exception:
            pass
