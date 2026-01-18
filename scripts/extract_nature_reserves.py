import json
import sys
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from api.extractors import OSMNatureReserveExtractor


@dataclass
class NatureReserve:
    id: str
    name: Optional[str]
    geometry: Dict[str, Any]
    tags: Dict[str, str]
    area_type: str


def to_geojson(reserves: List[NatureReserve]) -> Dict[str, Any]:
    features = []
    for reserve in reserves:
        feature = {
            "type": "Feature",
            "id": reserve.id,
            "properties": {
                "name": reserve.name,
                "area_type": reserve.area_type,
                **reserve.tags,
            },
            "geometry": reserve.geometry,
        }
        features.append(feature)

    return {"type": "FeatureCollection", "features": features}


def save_to_geojson(reserves: List[NatureReserve], filename: str) -> None:
    geojson = to_geojson(reserves)
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(geojson, f, indent=2, ensure_ascii=False)


def main():
    import argparse
    import sys

    extractor = OSMNatureReserveExtractor()

    netherlands_bbox = (3.2, 50.75, 7.2, 53.7)
    utrecht_bbox = (4.8, 51.9, 5.5, 52.3)

    parser = argparse.ArgumentParser(
        description="Extract nature reserves from OpenStreetMap"
    )
    parser.add_argument(
        "--province",
        choices=["utrecht"],
        help="Extract only from a specific province (currently only Utrecht supported)",
    )
    parser.add_argument(
        "bbox",
        nargs="?",
        help="Custom bounding box as: min_lon,min_lat,max_lon,max_lat",
    )

    args = parser.parse_args()

    bbox = netherlands_bbox
    bbox_name = "Netherlands"

    if args.province == "utrecht":
        bbox = utrecht_bbox
        bbox_name = "Utrecht province"
    elif args.bbox:
        try:
            coords = [float(x) for x in args.bbox.split(",")]
            if len(coords) == 4:
                bbox = tuple(coords)
                bbox_name = "custom"
            else:
                print(
                    "Bounding box must be 4 coordinates: min_lon,min_lat,max_lon,max_lat"
                )
                return
        except ValueError:
            print("Invalid bounding box format. Use: min_lon,min_lat,max_lon,max_lat")
            return

    print("Extracting nature reserves from OpenStreetMap...")
    print(f"Using {bbox_name} bounding box: {bbox}")

    try:
        reserve_dicts = extractor.extract(bbox=bbox)
        reserves = [
            NatureReserve(
                id=r["id"],
                name=r["name"],
                geometry=r["geometry"],
                tags=r["tags"],
                area_type=r["area_type"],
            )
            for r in reserve_dicts
        ]
        print(f"Found {len(reserves)} nature reserves")

        if reserves:
            output_file = "nature_reserves.geojson"
            save_to_geojson(reserves, output_file)
            print(f"Saved to {output_file}")

            print("\nSample reserves:")
            for reserve in reserves[:5]:
                print(f"  - {reserve.name or 'Unnamed'} ({reserve.area_type})")
        else:
            print("No nature reserves found.")

    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
