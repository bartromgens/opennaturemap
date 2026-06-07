from pathlib import Path
from typing import Optional, Tuple

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

from api.management.commands.export_geojson import REGION_BBOXES, parse_bbox


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
            default=getattr(settings, "VECTOR_TILE_MIN_ZOOM", 4),
            help=f"Minimum zoom level (default: {getattr(settings, 'VECTOR_TILE_MIN_ZOOM', 4)})",
        )
        parser.add_argument(
            "--max-zoom",
            type=int,
            default=getattr(settings, "VECTOR_TILE_MAX_ZOOM", 13),
            help=f"Maximum zoom level (default: {getattr(settings, 'VECTOR_TILE_MAX_ZOOM', 13)})",
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
            "--maximum-tile-bytes",
            type=int,
            default=300_000,
            metavar="BYTES",
            help="Max size per tile in bytes (default: 300000).",
        )
        parser.add_argument(
            "--low-detail",
            type=int,
            default=12,
            metavar="DETAIL",
            help="Detail (resolution) at zoom levels below max zoom; lower = smaller tiles (default: 12).",
        )
        parser.add_argument(
            "--minimum-detail",
            type=int,
            default=6,
            metavar="DETAIL",
            help="Minimum detail to try when a tile exceeds size limit (default: 6).",
        )
        parser.add_argument(
            "--simplification",
            type=float,
            default=30.0,
            metavar="SCALE",
            help="Simplification scale multiplier; higher = more aggressive simplification (default: 30.0).",
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
        geojson_output = options["geojson_output"]
        mbtiles_output = options["output"]
        min_zoom = options["min_zoom"]
        max_zoom = options["max_zoom"]
        layer_name = options["layer_name"]
        force = options["force"]
        maximum_tile_bytes = options["maximum_tile_bytes"]
        low_detail = options["low_detail"]
        minimum_detail = options["minimum_detail"]
        simplification = options["simplification"]
        no_coalesce = options["no_coalesce"]
        no_drop_smallest = options["no_drop_smallest"]
        bbox_str = options.get("bbox")

        bbox: Optional[Tuple[float, float, float, float]] = None
        if bbox_str:
            bbox = parse_bbox(bbox_str)
            if bbox is None:
                raise CommandError(
                    f"Invalid bbox: {bbox_str}. Use a region name or "
                    "min_lon,min_lat,max_lon,max_lat"
                )
            self.stdout.write(f"Using bounding box: {bbox}")

        geojson_path = Path(geojson_output)

        self.stdout.write("=" * 60)
        self.stdout.write("Step 1: Exporting GeoJSON from database")
        self.stdout.write("=" * 60)

        try:
            export_kwargs = {"output": str(geojson_path)}
            if bbox_str:
                export_kwargs["bbox"] = bbox_str
            call_command("export_geojson", **export_kwargs)
        except Exception as e:
            raise CommandError(f"Failed to export GeoJSON: {e}")

        if not geojson_path.exists():
            raise CommandError("GeoJSON export failed - file was not created")

        self.stdout.write("")
        self.stdout.write("=" * 60)
        self.stdout.write("Step 2: Converting GeoJSON to MBTiles")
        self.stdout.write("=" * 60)

        try:
            mbtiles_kwargs = {
                "input": str(geojson_path),
                "output": mbtiles_output,
                "min_zoom": min_zoom,
                "max_zoom": max_zoom,
                "layer_name": layer_name,
                "force": force,
                "maximum_tile_bytes": maximum_tile_bytes,
                "low_detail": low_detail,
                "minimum_detail": minimum_detail,
                "simplification": simplification,
                "no_coalesce": no_coalesce,
                "no_drop_smallest": no_drop_smallest,
            }
            if bbox_str:
                mbtiles_kwargs["bbox"] = bbox_str
            call_command("geojson_to_mbtiles", **mbtiles_kwargs)
        except Exception as e:
            raise CommandError(f"Failed to convert to MBTiles: {e}")

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("=" * 60))
        self.stdout.write(self.style.SUCCESS("Export and conversion complete!"))
        self.stdout.write(self.style.SUCCESS("=" * 60))
        self.stdout.write(f"MBTiles output: {Path(mbtiles_output).absolute()}")
        self.stdout.write(f"GeoJSON output: {geojson_path.absolute()}")
