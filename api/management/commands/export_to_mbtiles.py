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
        parser.add_argument(
            "--low-detail",
            type=int,
            default=10,
            metavar="DETAIL",
            help="Detail at lower zoom levels (default: 10, lower = smaller tiles).",
        )
        parser.add_argument(
            "--simplification",
            type=float,
            default=10.0,
            metavar="SCALE",
            help="Simplification scale multiplier (default: 10.0 for faster low-zoom rendering).",
        )
        parser.add_argument(
            "--no-coalesce",
            action="store_true",
            help="Use --drop-densest-as-needed instead of --coalesce-densest-as-needed.",
        )
        parser.add_argument(
            "--no-drop-smallest",
            action="store_true",
            help="Don't use --drop-smallest-as-needed.",
        )

    def handle(self, *args, **options):
        geojson_output = options["geojson_output"]
        mbtiles_output = options["output"]
        min_zoom = options["min_zoom"]
        max_zoom = options["max_zoom"]
        layer_name = options["layer_name"]
        force = options["force"]
        low_detail = options["low_detail"]
        simplification = options["simplification"]
        coalesce = not options["no_coalesce"]
        drop_smallest = not options["no_drop_smallest"]

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
                low_detail=low_detail,
                simplification=simplification,
                coalesce=coalesce,
                drop_smallest=drop_smallest,
            )
        except Exception as e:
            raise CommandError(f"Failed to convert to MBTiles: {e}")

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("=" * 60))
        self.stdout.write(self.style.SUCCESS("Export and conversion complete!"))
        self.stdout.write(self.style.SUCCESS("=" * 60))
        self.stdout.write(f"MBTiles output: {Path(mbtiles_output).absolute()}")
        self.stdout.write(f"GeoJSON output: {geojson_path.absolute()}")
