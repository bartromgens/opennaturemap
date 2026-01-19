import json
import subprocess
import shutil
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from django.core.management import call_command
from django.conf import settings
import tempfile
import os


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

    def handle(self, *args, **options):
        input_path = options.get("input")
        output_path = Path(options["output"])
        min_zoom = options["min_zoom"]
        max_zoom = options["max_zoom"]
        layer_name = options["layer_name"]
        force = options["force"]

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

        self.stdout.write(f"Reading GeoJSON from {input_path}...")
        try:
            with open(input_path, "r", encoding="utf-8") as f:
                geojson_data = json.load(f)
                feature_count = len(geojson_data.get("features", []))
                self.stdout.write(f"Found {feature_count} features in GeoJSON")
        except json.JSONDecodeError as e:
            raise CommandError(f"Invalid GeoJSON file: {e}")
        except Exception as e:
            raise CommandError(f"Error reading GeoJSON file: {e}")

        if feature_count == 0:
            raise CommandError("GeoJSON file contains no features")

        tippecanoe_path = self._find_tippecanoe()

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
                str(input_path),
            ]

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

    def _find_tippecanoe(self):
        tippecanoe_path = shutil.which("tippecanoe")

        if not tippecanoe_path:
            common_paths = [
                "/usr/local/bin/tippecanoe",
                "/usr/bin/tippecanoe",
                "/opt/homebrew/bin/tippecanoe",
            ]
            for path in common_paths:
                if os.path.exists(path) and os.access(path, os.X_OK):
                    tippecanoe_path = path
                    break

        if not tippecanoe_path:
            raise CommandError(
                "tippecanoe is not installed or not in PATH.\n"
                "Install it:\n"
                "  Ubuntu/Debian: sudo apt-get install tippecanoe\n"
                "  macOS: brew install tippecanoe\n"
                "  Or build from source: https://github.com/felt/tippecanoe"
            )

        if not os.path.exists(tippecanoe_path):
            raise CommandError(f"tippecanoe not found at {tippecanoe_path}")

        if not os.access(tippecanoe_path, os.X_OK):
            raise CommandError(f"tippecanoe at {tippecanoe_path} is not executable")

        result = subprocess.run(
            [tippecanoe_path, "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            version = (result.stdout or result.stderr or "").strip()
            if version:
                self.stdout.write(f"Using tippecanoe: {version} ({tippecanoe_path})")
            else:
                self.stdout.write(f"Using tippecanoe at {tippecanoe_path}")
        else:
            self.stdout.write(
                self.style.WARNING(
                    f"Could not verify tippecanoe version, but will attempt to use {tippecanoe_path}"
                )
            )

        return tippecanoe_path
