import subprocess
from pathlib import Path

import ijson

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

from api.management.utils import find_executable


class Command(BaseCommand):
    help = "Convert GeoJSON to MBTiles format for tileserver-gl"

    def add_arguments(self, parser):
        parser.add_argument(
            "--input",
            type=str,
            default=str(settings.BASE_DIR / "data" / "nature_reserves.geojson"),
            help="Input GeoJSON file path (default: data/nature_reserves.geojson)",
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
            "--maximum-tile-bytes",
            type=int,
            default=500_000,
            metavar="BYTES",
            help="Max size per tile in bytes (default: 500000). Tippecanoe default is 500000; increase if tiles exceed limit.",
        )
        parser.add_argument(
            "--low-detail",
            type=int,
            default=12,
            metavar="DETAIL",
            help="Detail (resolution) at zoom levels below max zoom; lower = smaller tiles (default: 12, tippecanoe default 12).",
        )
        parser.add_argument(
            "--minimum-detail",
            type=int,
            default=7,
            metavar="DETAIL",
            help="Minimum detail to try when a tile exceeds size limit; lower = more reduction allowed (default: 7, tippecanoe default 7).",
        )
        parser.add_argument(
            "--simplification",
            type=float,
            default=1.0,
            metavar="SCALE",
            help="Simplification scale multiplier; higher = more aggressive simplification (default: 1.0).",
        )
        parser.add_argument(
            "--coalesce",
            action="store_true",
            help="Use --coalesce-densest-as-needed instead of --drop-densest-as-needed (better for polygons).",
        )
        parser.add_argument(
            "--drop-smallest",
            action="store_true",
            help="Also use --drop-smallest-as-needed to drop small features when tiles are too big.",
        )

    def handle(self, *args, **options):
        input_path = options.get("input")
        output_path = Path(options["output"])
        min_zoom = options["min_zoom"]
        max_zoom = options["max_zoom"]
        layer_name = options["layer_name"]
        force = options["force"]
        maximum_tile_bytes = options["maximum_tile_bytes"]
        low_detail = options["low_detail"]
        minimum_detail = options["minimum_detail"]
        simplification = options["simplification"]
        coalesce = options["coalesce"]
        drop_smallest = options["drop_smallest"]

        if output_path.exists() and not force:
            raise CommandError(
                f"Output file {output_path} already exists. Use --force to overwrite."
            )

        default_input = str(settings.BASE_DIR / "data" / "nature_reserves.geojson")
        if not input_path:
            input_path = default_input

        input_path = Path(input_path)
        if not input_path.exists():
            self.stdout.write(
                f"Input file {input_path} not found, exporting GeoJSON from database..."
            )
            input_path = Path(default_input)
            try:
                call_command("export_geojson", output=str(input_path))
            except Exception as e:
                raise CommandError(f"Failed to export GeoJSON: {e}")

        if not input_path.exists():
            raise CommandError(f"Input file {input_path} does not exist")

        self.stdout.write(f"Counting features in {input_path}...")
        try:
            feature_count = 0
            with open(input_path, "rb") as f:
                for _ in ijson.items(f, "features.item"):
                    feature_count += 1
            self.stdout.write(f"Found {feature_count} features in GeoJSON")
        except ijson.JSONError as e:
            raise CommandError(f"Invalid GeoJSON file: {e}")
        except Exception as e:
            raise CommandError(f"Error reading GeoJSON file: {e}")

        if feature_count == 0:
            raise CommandError("GeoJSON file contains no features")

        tippecanoe_path = find_executable(
            "tippecanoe",
            [
                "/usr/local/bin/tippecanoe",
                "/usr/bin/tippecanoe",
                "/opt/homebrew/bin/tippecanoe",
            ],
            "tippecanoe is not installed or not in PATH.\n"
            "Install it:\n"
            "  Ubuntu/Debian: sudo apt-get install tippecanoe\n"
            "  macOS: brew install tippecanoe\n"
            "  Or build from source: https://github.com/felt/tippecanoe",
        )
        self._log_tippecanoe_version(tippecanoe_path)

        self.stdout.write(f"Converting to MBTiles (zoom {min_zoom}-{max_zoom})...")
        self.stdout.write(f"Output: {output_path.absolute()}")

        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)

            tippecanoe_cmd = [
                tippecanoe_path,
                "--output",
                str(output_path),
                "--layer",
                layer_name,
                "--minimum-zoom",
                str(min_zoom),
                "--maximum-zoom",
                str(max_zoom),
                "--maximum-tile-bytes",
                str(maximum_tile_bytes),
                "--low-detail",
                str(low_detail),
                "--minimum-detail",
                str(minimum_detail),
            ]

            if simplification != 1.0:
                tippecanoe_cmd.extend(["--simplification", str(simplification)])

            if coalesce:
                tippecanoe_cmd.append("--coalesce-densest-as-needed")
            else:
                tippecanoe_cmd.append("--drop-densest-as-needed")

            if drop_smallest:
                tippecanoe_cmd.append("--drop-smallest-as-needed")

            tippecanoe_cmd.extend(
                [
                    "--extend-zooms-if-still-dropping",
                    str(input_path),
                ]
            )

            if force:
                tippecanoe_cmd.insert(-1, "--force")

            result = subprocess.run(
                tippecanoe_cmd,
                capture_output=True,
                text=True,
                check=True,
            )

            if result.stdout:
                self.stdout.write(result.stdout)

            file_size = output_path.stat().st_size / (1024 * 1024)
            self.stdout.write(
                self.style.SUCCESS(
                    f"\nConversion complete: {output_path.absolute()} ({file_size:.2f} MB)"
                )
            )

        except subprocess.CalledProcessError as e:
            error_msg = e.stderr if e.stderr else str(e)
            raise CommandError(f"tippecanoe failed: {error_msg}")
        except FileNotFoundError:
            raise CommandError(
                "tippecanoe not found. Please install it:\n"
                "  Ubuntu/Debian: sudo apt-get install tippecanoe\n"
                "  macOS: brew install tippecanoe\n"
                "  Or build from source: https://github.com/felt/tippecanoe"
            )

    def _log_tippecanoe_version(self, tippecanoe_path: str) -> None:
        try:
            result = subprocess.run(
                [tippecanoe_path, "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                version = (result.stdout or result.stderr or "").strip()
                if version:
                    self.stdout.write(
                        f"Using tippecanoe: {version} ({tippecanoe_path})"
                    )
                else:
                    self.stdout.write(f"Using tippecanoe at {tippecanoe_path}")
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f"Could not verify tippecanoe version, but will attempt to use {tippecanoe_path}"
                    )
                )
        except Exception:
            pass
