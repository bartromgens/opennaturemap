import requests
import time
from typing import List, Dict, Any, Optional, Callable
import osm2geojson


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
        tags: Optional[List[tuple[str, str]]] = None,
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

    def query_overpass(
        self, query: str, output_callback: Optional[Callable[[str], None]] = None
    ) -> Dict[str, Any]:
        if output_callback is None:
            output_callback = print

        servers_to_try = [self.overpass_url] + [
            s for s in self.overpass_servers if s != self.overpass_url
        ]

        for attempt in range(self.max_retries):
            for server_url in servers_to_try:
                try:
                    if attempt > 0:
                        wait_time = 2**attempt
                        output_callback(
                            f"Retrying in {wait_time} seconds... (attempt {attempt + 1}/{self.max_retries})"
                        )
                        time.sleep(wait_time)

                    output_callback(f"Querying Overpass API: {server_url}")
                    response = requests.post(
                        server_url, data={"data": query}, timeout=self.timeout + 30
                    )

                    if response.status_code == 200:
                        return response.json()
                    elif response.status_code == 504:
                        output_callback(
                            f"Server timeout (504) from {server_url}, trying next server..."
                        )
                        continue
                    elif response.status_code == 429:
                        wait_time = 60 * (attempt + 1)
                        output_callback(
                            f"Rate limited (429), waiting {wait_time} seconds..."
                        )
                        time.sleep(wait_time)
                        continue
                    else:
                        error_msg = (
                            f"HTTP {response.status_code}: {response.text[:500]}"
                        )
                        if response.status_code == 400:
                            error_msg += f"\n\nQuery that failed:\n{query}"
                        raise requests.exceptions.HTTPError(error_msg)

                except requests.exceptions.Timeout:
                    output_callback(
                        f"Request timeout from {server_url}, trying next server..."
                    )
                    continue
                except requests.exceptions.RequestException as e:
                    if (
                        attempt == self.max_retries - 1
                        and server_url == servers_to_try[-1]
                    ):
                        raise
                    output_callback(
                        f"Request error from {server_url}: {e}, trying next server..."
                    )
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

    def parse_elements(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        geojson_data = osm2geojson.json2geojson(data, filter_used_refs=True)

        reserves: List[Dict[str, Any]] = []
        features = geojson_data.get("features", [])
        elements_by_id = {elem["id"]: elem for elem in data.get("elements", [])}

        for feature in features:
            properties = feature.get("properties", {})
            geometry = feature.get("geometry")

            if geometry is None:
                continue

            tags = {
                k: v
                for k, v in properties.items()
                if k not in ["id", "type", "@id", "@type"]
            }

            if not any(
                key in tags
                for key in [
                    "leisure",
                    "boundary",
                    "landuse",
                    "protect_class",
                    "natural",
                ]
            ):
                continue

            element_id = properties.get("@id") or properties.get("id")
            if isinstance(element_id, (int, float)):
                element_type = properties.get("@type", "way")
                element_id = f"{element_type}_{int(element_id)}"

            element_id_str = str(element_id)

            osm_element = None
            for elem in data.get("elements", []):
                elem_id = f"{elem.get('type', 'way')}_{elem.get('id', '')}"
                if elem_id == element_id_str or str(elem.get("id", "")) == str(
                    element_id
                ):
                    osm_element = elem
                    break

            if not osm_element:
                continue

            reserve = {
                "id": element_id_str,
                "name": tags.get("name") or tags.get("name:en") or None,
                "osm_data": osm_element,
                "geometry": geometry,
                "tags": tags,
                "area_type": self.determine_area_type(tags),
            }
            reserves.append(reserve)

        return reserves

    def extract(
        self,
        bbox: Optional[tuple[float, float, float, float]] = None,
        tags: Optional[List[tuple[str, str]]] = None,
        output_callback: Optional[Callable[[str], None]] = None,
    ) -> List[Dict[str, Any]]:
        query = self.build_query(bbox, tags)
        data = self.query_overpass(query, output_callback=output_callback)
        return self.parse_elements(data)
