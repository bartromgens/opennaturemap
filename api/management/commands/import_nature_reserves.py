import math
import requests
from datetime import timedelta
from typing import List, Tuple

from django.core.management.base import BaseCommand
from django.utils import timezone

from api.extractors import OSMNatureReserveExtractor
from api.geometry_utils import bbox_from_osm_geometry, reserve_geojson_features
from api.models import ImportGrid, NatureReserve, Operator

NETHERLANDS_BBOX: Tuple[float, float, float, float] = (3.2, 50.75, 7.2, 53.7)
SPAIN_BBOX: Tuple[float, float, float, float] = (-9.3, 36.0, 4.3, 43.8)
FRANCE_BBOX: Tuple[float, float, float, float] = (-5.5, 41.3, 9.6, 51.1)
SWITZERLAND_BBOX: Tuple[float, float, float, float] = (5.9, 45.8, 10.5, 47.8)
GERMANY_BBOX: Tuple[float, float, float, float] = (5.9, 47.3, 15.0, 55.1)
BELGIUM_BBOX: Tuple[float, float, float, float] = (2.5, 49.5, 6.4, 51.5)
ITALY_BBOX: Tuple[float, float, float, float] = (6.6, 36.6, 18.5, 47.1)
NORWAY_BBOX: Tuple[float, float, float, float] = (4.6, 57.9, 31.1, 71.2)


class Command(BaseCommand):
    help = (
        "Import nature reserves from OpenStreetMap (Overpass API). "
        "Default bbox is the Netherlands. Uses a grid of tiles for large areas; "
        "grid state is stored so imports can be resumed and grids can be refreshed by age."
    )

    TILE_SIZE_KM = 40.0

    def calculate_tile_size_degrees(
        self, center_lat: float, tile_size_km: float | None = None
    ) -> Tuple[float, float]:
        km = tile_size_km if tile_size_km is not None else self.TILE_SIZE_KM
        lat_degrees = km / 111.0
        lon_degrees = km / (111.0 * math.cos(math.radians(center_lat)))
        return (lon_degrees, lat_degrees)

    def should_split_bbox(
        self,
        bbox: Tuple[float, float, float, float],
        tile_size_km: float | None = None,
    ) -> bool:
        min_lon, min_lat, max_lon, max_lat = bbox
        center_lat = (min_lat + max_lat) / 2.0
        lon_degrees, lat_degrees = self.calculate_tile_size_degrees(
            center_lat, tile_size_km
        )
        bbox_lon_span = max_lon - min_lon
        bbox_lat_span = max_lat - min_lat
        return bbox_lon_span > lon_degrees or bbox_lat_span > lat_degrees

    def split_bbox_into_tiles(
        self,
        bbox: Tuple[float, float, float, float],
        tile_size_km: float | None = None,
    ) -> List[Tuple[float, float, float, float]]:
        min_lon, min_lat, max_lon, max_lat = bbox
        center_lat = (min_lat + max_lat) / 2.0
        lon_degrees, lat_degrees = self.calculate_tile_size_degrees(
            center_lat, tile_size_km
        )
        tiles = []
        current_lat = min_lat
        while current_lat < max_lat:
            tile_max_lat = min(current_lat + lat_degrees, max_lat)
            current_lon = min_lon
            while current_lon < max_lon:
                tile_max_lon = min(current_lon + lon_degrees, max_lon)
                tiles.append((current_lon, current_lat, tile_max_lon, tile_max_lat))
                current_lon += lon_degrees
            current_lat += lat_degrees
        return tiles

    def should_skip_grid(
        self,
        grid: ImportGrid,
        resume: bool,
        min_age_hours: float | None,
    ) -> bool:
        if resume and grid.success:
            return True
        if min_age_hours is not None and grid.last_updated is not None:
            if grid.last_updated >= timezone.now() - timedelta(hours=min_age_hours):
                return True
        return False

    def _operators_from_tags(self, tags: dict) -> List[Operator]:
        raw = (tags or {}).get("operator", "").strip()
        if not raw:
            return []
        result: List[Operator] = []
        for part in raw.split(";"):
            name = part.strip()
            if name:
                operator, _ = Operator.objects.get_or_create(name=name)
                result.append(operator)
        return result

    def process_tile_reserves(
        self,
        reserves: List[dict],
        output_callback,
    ) -> Tuple[int, int, int]:
        created_count = 0
        updated_count = 0
        error_count = 0
        for idx, reserve_data in enumerate(reserves, 1):
            try:
                tags = reserve_data.get("tags") or {}
                operator_list = self._operators_from_tags(tags)
                geometry = reserve_data.get("geometry") or (
                    reserve_data.get("osm_data") or {}
                ).get("geometry")
                bbox = bbox_from_osm_geometry(geometry)
                if bbox is None:
                    rid = reserve_data.get("id")
                    self.stdout.write(
                        self.style.WARNING(
                            f"  Reserve {idx} ({rid}): no geometry, skipping"
                        )
                    )
                    continue
                min_lon, min_lat, max_lon, max_lat = bbox
                protect_class = (tags.get("protect_class") or "").strip() or None
                geojson_list = reserve_geojson_features(
                    reserve_data["osm_data"],
                    reserve_data["id"],
                    reserve_data.get("name"),
                    reserve_data["area_type"],
                    [o.id for o in operator_list],
                    reserve_data.get("tags") or {},
                    protect_class,
                )
                defaults: dict = {
                    "name": reserve_data["name"],
                    "osm_data": reserve_data["osm_data"],
                    "geojson": geojson_list if geojson_list else None,
                    "tags": reserve_data["tags"],
                    "area_type": reserve_data["area_type"],
                    "protect_class": protect_class,
                    "min_lon": min_lon,
                    "min_lat": min_lat,
                    "max_lon": max_lon,
                    "max_lat": max_lat,
                }
                reserve, created = NatureReserve.objects.update_or_create(
                    id=reserve_data["id"],
                    defaults=defaults,
                )
                reserve.operators.set(operator_list)
                if created:
                    created_count += 1
                else:
                    updated_count += 1
                if idx % 100 == 0:
                    output_callback(f"  Processed {idx}/{len(reserves)} reserves...")
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  Reserve {idx}: Error - {e}"))
                error_count += 1
        return created_count, updated_count, error_count

    def add_arguments(self, parser):
        parser.add_argument(
            "--region",
            choices=[
                "netherlands",
                "spain",
                "france",
                "switzerland",
                "germany",
                "belgium",
                "italy",
                "norway",
            ],
            default="netherlands",
            help="Country/region to import (default: netherlands)",
        )
        parser.add_argument(
            "--province",
            choices=["utrecht", "friesland"],
            help="Extract only from a specific province (Utrecht or Friesland, Netherlands only)",
        )
        parser.add_argument(
            "--bbox",
            type=str,
            help="Custom bounding box as: min_lon,min_lat,max_lon,max_lat (default: Netherlands)",
        )
        parser.add_argument(
            "--center",
            type=str,
            metavar="LON,LAT",
            help=f"Single coordinate lon,lat; imports one default-sized tile (~{self.TILE_SIZE_KM}x{self.TILE_SIZE_KM} km) centered on this point",
        )
        parser.add_argument(
            "--test-region",
            action="store_true",
            help="Import from a small test region in Utrecht around coordinate 52.11695/5.21434",
        )
        parser.add_argument(
            "--test-de-deelen",
            action="store_true",
            help="Import from a small test area around De Deelen (relation 7010743) in Friesland",
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Clear existing nature reserves before importing",
        )
        parser.add_argument(
            "--resume",
            action="store_true",
            help="Skip grids that were successfully loaded last time (retry only failed or new grids)",
        )
        parser.add_argument(
            "--min-age",
            type=float,
            metavar="HOURS",
            help="Only process grids that were never updated or last updated more than HOURS ago",
        )
        parser.add_argument(
            "--tile-size",
            type=float,
            default=None,
            metavar="KM",
            help=f"Grid tile size in km (default: {self.TILE_SIZE_KM}). Smaller tiles = lighter Overpass queries and fewer timeouts, but more requests.",
        )

    def handle(self, *args, **options):
        extractor = OSMNatureReserveExtractor()

        def output_callback(msg):
            self.stdout.write(msg)

        utrecht_bbox = (4.8, 51.9, 5.5, 52.3)
        friesland_bbox = (4.8697, 52.8008, 6.4288, 53.5112)
        test_region_bbox = (5.14134, 52.07195, 5.28734, 52.16195)
        de_deelen_bbox = (5.8, 52.95, 6.0, 53.1)

        bbox = NETHERLANDS_BBOX
        bbox_name = "Netherlands"
        area_iso = "NL"

        if options["test_region"]:
            bbox = test_region_bbox
            bbox_name = "test region (Utrecht, 52.11695/5.21434)"
            area_iso = None
        elif options["test_de_deelen"]:
            bbox = de_deelen_bbox
            bbox_name = "test area (De Deelen, relation 7010743)"
            area_iso = None
        elif options["province"] == "utrecht":
            bbox = utrecht_bbox
            bbox_name = "Utrecht province"
            area_iso = "NL"
        elif options["province"] == "friesland":
            bbox = friesland_bbox
            bbox_name = "Friesland province"
            area_iso = "NL"
        elif options["region"] == "spain":
            bbox = SPAIN_BBOX
            bbox_name = "Spain"
            area_iso = "ES"
        elif options["region"] == "france":
            bbox = FRANCE_BBOX
            bbox_name = "France"
            area_iso = "FR"
        elif options["region"] == "switzerland":
            bbox = SWITZERLAND_BBOX
            bbox_name = "Switzerland"
            area_iso = "CH"
        elif options["region"] == "germany":
            bbox = GERMANY_BBOX
            bbox_name = "Germany"
            area_iso = "DE"
        elif options["region"] == "belgium":
            bbox = BELGIUM_BBOX
            bbox_name = "Belgium"
            area_iso = "BE"
        elif options["region"] == "italy":
            bbox = ITALY_BBOX
            bbox_name = "Italy"
            area_iso = "IT"
        elif options["region"] == "norway":
            bbox = NORWAY_BBOX
            bbox_name = "Norway"
            area_iso = "NO"
        elif options["bbox"]:
            try:
                coords = [float(x) for x in options["bbox"].split(",")]
                if len(coords) == 4:
                    bbox = tuple(coords)
                    bbox_name = "custom"
                    area_iso = None
                else:
                    self.stdout.write(
                        self.style.ERROR(
                            "Bounding box must be 4 coordinates: min_lon,min_lat,max_lon,max_lat"
                        )
                    )
                    return
            except ValueError:
                self.stdout.write(
                    self.style.ERROR(
                        "Invalid bounding box format. Use: min_lon,min_lat,max_lon,max_lat"
                    )
                )
                return
        elif options["center"]:
            try:
                coords = [float(x) for x in options["center"].split(",")]
                if len(coords) == 2:
                    center_lon, center_lat = coords
                    lon_degrees, lat_degrees = self.calculate_tile_size_degrees(
                        center_lat
                    )
                    half_lon = lon_degrees / 2.0
                    half_lat = lat_degrees / 2.0
                    bbox = (
                        center_lon - half_lon,
                        center_lat - half_lat,
                        center_lon + half_lon,
                        center_lat + half_lat,
                    )
                    bbox_name = f"center {center_lon},{center_lat}"
                    area_iso = None
                else:
                    self.stdout.write(
                        self.style.ERROR("Center must be 2 coordinates: lon,lat")
                    )
                    return
            except ValueError:
                self.stdout.write(
                    self.style.ERROR("Invalid center format. Use: lon,lat")
                )
                return

        if options["clear"]:
            count = NatureReserve.objects.count()
            NatureReserve.objects.all().delete()
            self.stdout.write(
                self.style.SUCCESS(f"Cleared {count} existing nature reserves")
            )

        self.stdout.write("Extracting nature reserves from OpenStreetMap...")
        self.stdout.write(f"Using {bbox_name} bounding box: {bbox}")
        if options["resume"]:
            self.stdout.write("Resume mode: skipping grids that succeeded previously")
        if options["min_age"] is not None:
            self.stdout.write(
                f"Min age: only processing grids older than {options['min_age']} hours"
            )

        tile_size_km = options.get("tile_size")
        if tile_size_km is not None:
            self.stdout.write(f"Using tile size: {tile_size_km} km")
        try:
            if self.should_split_bbox(bbox, tile_size_km):
                tiles = self.split_bbox_into_tiles(bbox, tile_size_km)
                km = tile_size_km if tile_size_km is not None else self.TILE_SIZE_KM
                self.stdout.write(
                    f"Splitting area into {len(tiles)} tiles " f"(~{km}x{km} km each)"
                )

                total_created = 0
                total_updated = 0
                total_errors = 0
                processed = 0

                for tile_idx, tile_bbox in enumerate(tiles, 1):
                    min_lon, min_lat, max_lon, max_lat = tile_bbox
                    grid, _ = ImportGrid.objects.get_or_create(
                        min_lon=min_lon,
                        min_lat=min_lat,
                        max_lon=max_lon,
                        max_lat=max_lat,
                        defaults={
                            "grid_number": tile_idx,
                            "success": False,
                        },
                    )

                    if self.should_skip_grid(
                        grid,
                        resume=options["resume"],
                        min_age_hours=options["min_age"],
                    ):
                        self.stdout.write(
                            f"\nSkipping tile {tile_idx}/{len(tiles)}: {tile_bbox} "
                            f"(success={grid.success}, last_updated={grid.last_updated})"
                        )
                        continue

                    self.stdout.write(
                        f"\nProcessing tile {tile_idx}/{len(tiles)}: {tile_bbox}"
                    )
                    try:
                        tile_reserves = extractor.extract(
                            bbox=tile_bbox,
                            area_iso=area_iso,
                            output_callback=output_callback,
                        )
                        output_callback(
                            f"  Found {len(tile_reserves)} reserves in this tile"
                        )

                        created, updated, errs = self.process_tile_reserves(
                            tile_reserves, output_callback
                        )
                        total_created += created
                        total_updated += updated
                        total_errors += errs
                        processed += 1

                        grid.grid_number = tile_idx
                        grid.last_updated = timezone.now()
                        grid.reserves_created_count = created
                        grid.reserves_updated_count = updated
                        grid.success = True
                        grid.error_message = None
                        grid.save()
                        output_callback(
                            f"  Grid saved: created={created}, updated={updated}, errors={errs}"
                        )
                    except requests.exceptions.RequestException as e:
                        self.stdout.write(
                            self.style.WARNING(
                                f"  Error querying tile {tile_idx}: {e}. Continuing..."
                            )
                        )
                        grid.grid_number = tile_idx
                        grid.last_updated = timezone.now()
                        grid.reserves_created_count = 0
                        grid.reserves_updated_count = 0
                        grid.success = False
                        grid.error_message = str(e)
                        grid.save()
                    except Exception as e:
                        self.stdout.write(
                            self.style.ERROR(f"  Tile {tile_idx}: {e}. Continuing...")
                        )
                        grid.grid_number = tile_idx
                        grid.last_updated = timezone.now()
                        grid.success = False
                        grid.error_message = str(e)
                        grid.save()

                self.stdout.write(self.style.SUCCESS("\nImport complete (gridded):"))
                self.stdout.write(f"  Tiles processed: {processed}/{len(tiles)}")
                self.stdout.write(f"  Created: {total_created}")
                self.stdout.write(f"  Updated: {total_updated}")
                self.stdout.write(f"  Errors: {total_errors}")
                self.stdout.write(
                    f"  Total in database: {NatureReserve.objects.count()}"
                )
            else:
                min_lon, min_lat, max_lon, max_lat = bbox
                grid, _ = ImportGrid.objects.get_or_create(
                    min_lon=min_lon,
                    min_lat=min_lat,
                    max_lon=max_lon,
                    max_lat=max_lat,
                    defaults={"grid_number": 1, "success": False},
                )

                if self.should_skip_grid(
                    grid,
                    resume=options["resume"],
                    min_age_hours=options["min_age"],
                ):
                    self.stdout.write(
                        f"Skipping single grid (success={grid.success}, "
                        f"last_updated={grid.last_updated})"
                    )
                    return

                reserves = extractor.extract(
                    bbox=bbox,
                    area_iso=area_iso,
                    output_callback=output_callback,
                )
                self.stdout.write(f"Found {len(reserves)} nature reserves")

                created, updated, error_count = self.process_tile_reserves(
                    reserves, output_callback
                )

                grid.grid_number = 1
                grid.last_updated = timezone.now()
                grid.reserves_created_count = created
                grid.reserves_updated_count = updated
                grid.success = True
                grid.error_message = None
                grid.save()

                self.stdout.write(self.style.SUCCESS("\nImport complete:"))
                self.stdout.write(f"  Created: {created}")
                self.stdout.write(f"  Updated: {updated}")
                self.stdout.write(f"  Errors: {error_count}")
                self.stdout.write(
                    f"  Total in database: {NatureReserve.objects.count()}"
                )

                if reserves:
                    self.stdout.write("\nSample reserves:")
                    for reserve_data in reserves[:5]:
                        self.stdout.write(
                            f"  - {reserve_data['name'] or 'Unnamed'} "
                            f"({reserve_data['area_type']})"
                        )

        except requests.exceptions.RequestException as e:
            self.stdout.write(self.style.ERROR(f"Error querying Overpass API: {e}"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error: {e}"))
