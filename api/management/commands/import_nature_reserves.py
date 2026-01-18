import requests
from django.core.management.base import BaseCommand
from api.models import NatureReserve
from api.extractors import OSMNatureReserveExtractor


class Command(BaseCommand):
    help = "Import nature reserves from OpenStreetMap using Overpass API"

    def add_arguments(self, parser):
        parser.add_argument(
            "--province",
            choices=["utrecht"],
            help="Extract only from a specific province (currently only Utrecht supported)",
        )
        parser.add_argument(
            "--bbox",
            type=str,
            help="Custom bounding box as: min_lon,min_lat,max_lon,max_lat",
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

        bbox = netherlands_bbox
        bbox_name = "Netherlands"

        if options["province"] == "utrecht":
            bbox = utrecht_bbox
            bbox_name = "Utrecht province"
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
