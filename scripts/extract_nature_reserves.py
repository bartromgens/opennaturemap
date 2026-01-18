import json
import requests
import time
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import osm2geojson


@dataclass
class NatureReserve:
    id: str
    name: Optional[str]
    geometry: Dict[str, Any]
    tags: Dict[str, str]
    area_type: str


class OSMNatureReserveExtractor:
    def __init__(self, overpass_url: str = "https://overpass-api.de/api/interpreter"):
        self.overpass_url = overpass_url
        self.overpass_servers = [
            "https://overpass-api.de/api/interpreter",
            "https://overpass.kumi.systems/api/interpreter",
            "https://overpass.openstreetmap.ru/api/interpreter",
        ]
        self.timeout = 180
        self.max_retries = 3

    def build_query(
        self,
        bbox: Optional[tuple[float, float, float, float]] = None,
        tags: Optional[List[tuple[str, str]]] = None
    ) -> str:
        if tags is None:
            tags = [
                ("leisure", "nature_reserve"),
                ("boundary", "protected_area"),
                ("landuse", "conservation"),
            ]

        bbox_filter = ""
        if bbox:
            min_lon, min_lat, max_lon, max_lat = bbox
            bbox_filter = f"({min_lat},{min_lon},{max_lat},{max_lon})"

        query_parts = []
        for key, value in tags:
            if bbox:
                query_parts.append(f'  way["{key}"="{value}"]{bbox_filter};')
                query_parts.append(f'  relation["{key}"="{value}"]{bbox_filter};')
            else:
                query_parts.append(f'  way["{key}"="{value}"];')
                query_parts.append(f'  relation["{key}"="{value}"];')

        query_timeout = min(self.timeout, 90)
        query = f"""[out:json][timeout:{query_timeout}];
(
{chr(10).join(query_parts)}
);
(._;>;);
out geom;"""
        return query

    def query_overpass(self, query: str) -> Dict[str, Any]:
        servers_to_try = [self.overpass_url] + [s for s in self.overpass_servers if s != self.overpass_url]
        
        for attempt in range(self.max_retries):
            for server_url in servers_to_try:
                try:
                    if attempt > 0:
                        wait_time = 2 ** attempt
                        print(f"Retrying in {wait_time} seconds... (attempt {attempt + 1}/{self.max_retries})")
                        time.sleep(wait_time)
                    
                    print(f"Querying Overpass API: {server_url}")
                    response = requests.post(
                        server_url,
                        data={"data": query},
                        timeout=self.timeout + 30
                    )
                    
                    if response.status_code == 200:
                        return response.json()
                    elif response.status_code == 504:
                        print(f"Server timeout (504) from {server_url}, trying next server...")
                        continue
                    elif response.status_code == 429:
                        wait_time = 60 * (attempt + 1)
                        print(f"Rate limited (429), waiting {wait_time} seconds...")
                        time.sleep(wait_time)
                        continue
                    else:
                        error_msg = f"HTTP {response.status_code}: {response.text[:500]}"
                        if response.status_code == 400:
                            error_msg += f"\n\nQuery that failed:\n{query}"
                        raise requests.exceptions.HTTPError(error_msg)
                        
                except requests.exceptions.Timeout:
                    print(f"Request timeout from {server_url}, trying next server...")
                    continue
                except requests.exceptions.RequestException as e:
                    if attempt == self.max_retries - 1 and server_url == servers_to_try[-1]:
                        raise
                    print(f"Request error from {server_url}: {e}, trying next server...")
                    continue
        
        raise requests.exceptions.RequestException(
            f"Failed to query Overpass API after {self.max_retries} attempts across {len(servers_to_try)} servers"
        )

    def determine_area_type(self, tags: Dict[str, str]) -> str:
        if tags.get("leisure") == "nature_reserve":
            return "nature_reserve"
        elif tags.get("boundary") == "protected_area":
            protect_class = tags.get("protect_class", "unknown")
            return f"protected_area_class_{protect_class}"
        elif tags.get("landuse") == "conservation":
            return "conservation"
        else:
            return "other"

    def parse_elements(self, data: Dict[str, Any]) -> List[NatureReserve]:
        geojson_data = osm2geojson.json2geojson(data, filter_used_refs=True)
        
        reserves: List[NatureReserve] = []
        features = geojson_data.get("features", [])
        
        for feature in features:
            properties = feature.get("properties", {})
            geometry = feature.get("geometry")
            
            if geometry is None:
                continue
            
            tags = {k: v for k, v in properties.items() if k not in ["id", "type", "@id", "@type"]}
            
            if not any(key in tags for key in ["leisure", "boundary", "landuse", "protect_class", "natural"]):
                continue
            
            element_id = properties.get("@id") or properties.get("id") or f"feature_{len(reserves)}"
            if isinstance(element_id, (int, float)):
                element_type = properties.get("@type", "way")
                element_id = f"{element_type}_{int(element_id)}"
            
            reserve = NatureReserve(
                id=str(element_id),
                name=tags.get("name") or tags.get("name:en") or None,
                geometry=geometry,
                tags=tags,
                area_type=self.determine_area_type(tags)
            )
            reserves.append(reserve)

        return reserves

    def extract(
        self,
        bbox: Optional[tuple[float, float, float, float]] = None,
        tags: Optional[List[tuple[str, str]]] = None
    ) -> List[NatureReserve]:
        query = self.build_query(bbox, tags)
        data = self.query_overpass(query)
        return self.parse_elements(data)

    def to_geojson(self, reserves: List[NatureReserve]) -> Dict[str, Any]:
        features = []
        for reserve in reserves:
            feature = {
                "type": "Feature",
                "id": reserve.id,
                "properties": {
                    "name": reserve.name,
                    "area_type": reserve.area_type,
                    **reserve.tags
                },
                "geometry": reserve.geometry
            }
            features.append(feature)

        return {
            "type": "FeatureCollection",
            "features": features
        }

    def save_to_geojson(self, reserves: List[NatureReserve], filename: str) -> None:
        geojson = self.to_geojson(reserves)
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
        help="Extract only from a specific province (currently only Utrecht supported)"
    )
    parser.add_argument(
        "bbox",
        nargs="?",
        help="Custom bounding box as: min_lon,min_lat,max_lon,max_lat"
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
                print("Bounding box must be 4 coordinates: min_lon,min_lat,max_lon,max_lat")
                return
        except ValueError:
            print("Invalid bounding box format. Use: min_lon,min_lat,max_lon,max_lat")
            return
    
    print("Extracting nature reserves from OpenStreetMap...")
    print(f"Using {bbox_name} bounding box: {bbox}")
    
    try:
        reserves = extractor.extract(bbox=bbox)
        print(f"Found {len(reserves)} nature reserves")
        
        if reserves:
            output_file = "nature_reserves.geojson"
            extractor.save_to_geojson(reserves, output_file)
            print(f"Saved to {output_file}")
            
            print("\nSample reserves:")
            for reserve in reserves[:5]:
                print(f"  - {reserve.name or 'Unnamed'} ({reserve.area_type})")
        else:
            print("No nature reserves found.")
            
    except requests.exceptions.RequestException as e:
        print(f"Error querying Overpass API: {e}")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
