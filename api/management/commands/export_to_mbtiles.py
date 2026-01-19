from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from django.core.management import call_command
from django.conf import settings


class Command(BaseCommand):
    help = "Export NatureReserves to GeoJSON and convert to MBTiles format"

    def add_arguments(self, parser):
        parser.add_argument(
            "--geojson-output",
            type=str,
            default=str(settings.BASE_DIR / "data" / "nature_reserves.geojson"),
            help="Intermediate GeoJSON file path (default: data/nature_reserves.geojson)",
        )
        parser.add_argument(
            "--output",
            type=str,
            default=str(settings.BASE_DIR / "data" / "nature_reserves.mbtiles"),
            help="Output MBTiles file path (default: data/nature_reserves.mbtiles)",
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
            "--layer-name",
            type=str,
            default="nature_reserves",
            help="Layer name in MBTiles (default: nature_reserves)",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Overwrite output file if it exists",
        )

    def handle(self, *args, **options):
        geojson_output = options["geojson_output"]
        mbtiles_output = options["output"]
        min_zoom = options["min_zoom"]
        max_zoom = options["max_zoom"]
        layer_name = options["layer_name"]
        force = options["force"]

        geojson_path = Path(geojson_output)

        self.stdout.write("=" * 60)
        self.stdout.write("Step 1: Exporting GeoJSON from database")
        self.stdout.write("=" * 60)

        try:
            call_command("export_geojson", output=str(geojson_path))
        except Exception as e:
            raise CommandError(f"Failed to export GeoJSON: {e}")

        if not geojson_path.exists():
            raise CommandError("GeoJSON export failed - file was not created")

        self.stdout.write("")
        self.stdout.write("=" * 60)
        self.stdout.write("Step 2: Converting GeoJSON to MBTiles")
        self.stdout.write("=" * 60)

        try:
            call_command(
                "geojson_to_mbtiles",
                input=str(geojson_path),
                output=mbtiles_output,
                min_zoom=min_zoom,
                max_zoom=max_zoom,
                layer_name=layer_name,
                force=force,
            )
        except Exception as e:
            raise CommandError(f"Failed to convert to MBTiles: {e}")

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("=" * 60))
        self.stdout.write(self.style.SUCCESS("Export and conversion complete!"))
        self.stdout.write(self.style.SUCCESS("=" * 60))
        self.stdout.write(f"MBTiles output: {Path(mbtiles_output).absolute()}")
        self.stdout.write(f"GeoJSON output: {geojson_path.absolute()}")
