import math
import requests
from typing import List, Tuple
from django.core.management.base import BaseCommand
from api.models import NatureReserve
from api.extractors import OSMNatureReserveExtractor


class Command(BaseCommand):
    help = "Import nature reserves from OpenStreetMap using Overpass API"

    TILE_SIZE_KM = 30.0

    def calculate_tile_size_degrees(self, center_lat: float) -> Tuple[float, float]:
        # 1 degree of latitude ≈ 111 km (constant)
        lat_degrees = self.TILE_SIZE_KM / 111.0

        # 1 degree of longitude ≈ 111 * cos(latitude) km
        lon_degrees = self.TILE_SIZE_KM / (111.0 * math.cos(math.radians(center_lat)))

        return (lon_degrees, lat_degrees)

    def should_split_bbox(self, bbox: Tuple[float, float, float, float]) -> bool:
        min_lon, min_lat, max_lon, max_lat = bbox
        center_lat = (min_lat + max_lat) / 2.0

        lon_degrees, lat_degrees = self.calculate_tile_size_degrees(center_lat)

        bbox_lon_span = max_lon - min_lon
        bbox_lat_span = max_lat - min_lat

        # Split if the bbox is larger than one tile in either dimension
        return bbox_lon_span > lon_degrees or bbox_lat_span > lat_degrees

    def split_bbox_into_tiles(
        self, bbox: Tuple[float, float, float, float]
    ) -> List[Tuple[float, float, float, float]]:
        min_lon, min_lat, max_lon, max_lat = bbox
        center_lat = (min_lat + max_lat) / 2.0

        lon_degrees, lat_degrees = self.calculate_tile_size_degrees(center_lat)

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

    def add_arguments(self, parser):
        parser.add_argument(
            "--province",
            choices=["utrecht", "friesland"],
            help="Extract only from a specific province (Utrecht or Friesland)",
        )
        parser.add_argument(
            "--bbox",
            type=str,
            help="Custom bounding box as: min_lon,min_lat,max_lon,max_lat",
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

    def handle(self, *args, **options):
        extractor = OSMNatureReserveExtractor()

        def output_callback(msg):
            self.stdout.write(msg)

        netherlands_bbox = (3.2, 50.75, 7.2, 53.7)
        utrecht_bbox = (4.8, 51.9, 5.5, 52.3)
        friesland_bbox = (4.8697, 52.8008, 6.4288, 53.5112)
        test_region_bbox = (5.14134, 52.07195, 5.28734, 52.16195)
        de_deelen_bbox = (5.8, 52.95, 6.0, 53.1)

        bbox = netherlands_bbox
        bbox_name = "Netherlands"

        if options["test_region"]:
            bbox = test_region_bbox
            bbox_name = "test region (Utrecht, 52.11695/5.21434)"
        elif options["test_de_deelen"]:
            bbox = de_deelen_bbox
            bbox_name = "test area (De Deelen, relation 7010743)"
        elif options["province"] == "utrecht":
            bbox = utrecht_bbox
            bbox_name = "Utrecht province"
        elif options["province"] == "friesland":
            bbox = friesland_bbox
            bbox_name = "Friesland province"
        elif options["bbox"]:
            try:
                coords = [float(x) for x in options["bbox"].split(",")]
                if len(coords) == 4:
                    bbox = tuple(coords)
                    bbox_name = "custom"
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

        if options["clear"]:
            count = NatureReserve.objects.count()
            NatureReserve.objects.all().delete()
            self.stdout.write(
                self.style.SUCCESS(f"Cleared {count} existing nature reserves")
            )

        self.stdout.write(f"Extracting nature reserves from OpenStreetMap...")
        self.stdout.write(f"Using {bbox_name} bounding box: {bbox}")

        try:
            # Check if we need to split into tiles
            if self.should_split_bbox(bbox):
                tiles = self.split_bbox_into_tiles(bbox)
                self.stdout.write(
                    f"Splitting area into {len(tiles)} tiles (~{self.TILE_SIZE_KM}x{self.TILE_SIZE_KM} km each)"
                )

                all_reserves = {}
                for tile_idx, tile_bbox in enumerate(tiles, 1):
                    self.stdout.write(
                        f"\nProcessing tile {tile_idx}/{len(tiles)}: {tile_bbox}"
                    )
                    try:
                        tile_reserves = extractor.extract(
                            bbox=tile_bbox, output_callback=output_callback
                        )
                        # Deduplicate by ID (reserves might appear in multiple tiles)
                        for reserve in tile_reserves:
                            all_reserves[reserve["id"]] = reserve
                        self.stdout.write(
                            f"  Found {len(tile_reserves)} reserves in this tile "
                            f"(total unique: {len(all_reserves)})"
                        )
                    except requests.exceptions.RequestException as e:
                        self.stdout.write(
                            self.style.WARNING(
                                f"  Error querying tile {tile_idx}: {e}. Continuing with next tile..."
                            )
                        )
                        continue

                reserves = list(all_reserves.values())
                self.stdout.write(f"\nTotal unique reserves found: {len(reserves)}")
            else:
                reserves = extractor.extract(bbox=bbox, output_callback=output_callback)
                self.stdout.write(f"Found {len(reserves)} nature reserves")

            created_count = 0
            updated_count = 0
            error_count = 0

            for idx, reserve_data in enumerate(reserves, 1):
                try:
                    reserve, created = NatureReserve.objects.update_or_create(
                        id=reserve_data["id"],
                        defaults={
                            "name": reserve_data["name"],
                            "osm_data": reserve_data["osm_data"],
                            "tags": reserve_data["tags"],
                            "area_type": reserve_data["area_type"],
                        },
                    )

                    if created:
                        created_count += 1
                    else:
                        updated_count += 1

                    if idx % 100 == 0:
                        self.stdout.write(
                            f"  Processed {idx}/{len(reserves)} reserves..."
                        )

                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"  Reserve {idx}: Error - {e}"))
                    error_count += 1
                    continue

            self.stdout.write(self.style.SUCCESS(f"\nImport complete:"))
            self.stdout.write(f"  Created: {created_count}")
            self.stdout.write(f"  Updated: {updated_count}")
            self.stdout.write(f"  Errors: {error_count}")
            self.stdout.write(f"  Total in database: {NatureReserve.objects.count()}")

            if reserves:
                self.stdout.write("\nSample reserves:")
                for reserve_data in reserves[:5]:
                    self.stdout.write(
                        f"  - {reserve_data['name'] or 'Unnamed'} ({reserve_data['area_type']})"
                    )

        except requests.exceptions.RequestException as e:
            self.stdout.write(self.style.ERROR(f"Error querying Overpass API: {e}"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error: {e}"))
