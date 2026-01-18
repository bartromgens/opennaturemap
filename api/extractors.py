import requests
import time
from typing import List, Dict, Any, Optional, Callable


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

    def extract_relation_geometry(
        self, relation: Dict[str, Any], all_elements: List[Dict[str, Any]]
    ) -> Optional[List[Any]]:
        """Extract geometry from a relation by constructing it from member ways."""
        geometry = relation.get("geometry")
        if geometry:
            return geometry

        members = relation.get("members", [])
        if not members:
            return None

        # Build a map of way IDs to their geometries for quick lookup
        way_geometries: Dict[int, list] = {}
        for elem in all_elements:
            if elem.get("type") == "way" and "geometry" in elem:
                way_id = elem.get("id")
                if way_id is not None:
                    way_geometries[int(way_id)] = elem.get("geometry", [])

        # Collect outer and inner rings
        outer_rings: List[List[Dict[str, float]]] = []
        inner_rings: List[List[Dict[str, float]]] = []

        for member in members:
            if member.get("type") != "way":
                continue

            way_ref = member.get("ref")
            if way_ref is None:
                continue

            way_geom = way_geometries.get(int(way_ref))
            if not way_geom:
                continue

            role = member.get("role", "")
            if role == "outer":
                outer_rings.append(way_geom)
            elif role == "inner":
                inner_rings.append(way_geom)

        if not outer_rings:
            return None

        # For multipolygon, combine all rings
        # If there's only one outer ring, return it directly (with inner rings if any)
        if len(outer_rings) == 1 and not inner_rings:
            return outer_rings[0]

        # For multiple rings, we need to structure as MultiPolygon
        # Return as a list of polygons (each polygon is [outer, inner1, inner2, ...])
        result: List[List[List[Dict[str, float]]]] = []
        for outer in outer_rings:
            polygon = [outer]
            # Associate inner rings with the nearest outer ring (simplified)
            # In a full implementation, we'd check which inner rings are inside which outer
            result.append(polygon)

        # If we have inner rings but only one outer, add them to that outer
        if len(result) == 1 and inner_rings:
            result[0].extend(inner_rings)

        return result if len(result) > 1 else (result[0] if result else None)

    def parse_elements(
        self,
        data: Dict[str, Any],
        output_callback: Optional[Callable[[str], None]] = None,
    ) -> List[Dict[str, Any]]:
        reserves: List[Dict[str, Any]] = []
        elements = data.get("elements", [])

        if output_callback:
            output_callback(f"Processing {len(elements)} OSM elements")

        filtered_count = 0
        no_geometry_count = 0
        no_tags_count = 0
        node_count = 0
        relation_count = 0

        for elem in elements:
            elem_type = elem.get("type")
            elem_id = elem.get("id")

            if elem_type == "node":
                node_count += 1
                filtered_count += 1
                continue

            if elem_id is None:
                filtered_count += 1
                continue

            if isinstance(elem_id, (int, float)):
                element_id_str = f"{elem_type}_{int(elem_id)}"
            else:
                element_id_str = str(elem_id)

            tags = elem.get("tags", {})

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
                no_tags_count += 1
                filtered_count += 1
                continue

            # Handle geometry extraction
            geometry = elem.get("geometry")
            
            # For relations (especially multipolygons), try to extract geometry from members
            if elem_type == "relation" and (geometry is None or geometry == []):
                relation_count += 1
                geometry = self.extract_relation_geometry(elem, elements)
                if geometry is None:
                    no_geometry_count += 1
                    filtered_count += 1
                    continue

            # For ways, geometry is required
            if elem_type == "way" and geometry is None:
                no_geometry_count += 1
                filtered_count += 1
                continue

            reserve = {
                "id": element_id_str,
                "name": tags.get("name") or tags.get("name:en") or None,
                "osm_data": elem,
                "geometry": geometry,
                "tags": tags,
                "area_type": self.determine_area_type(tags),
            }
            reserves.append(reserve)

        if output_callback:
            output_callback(
                f"Filtered out {filtered_count} elements: "
                f"{node_count} nodes, {no_geometry_count} no geometry, {no_tags_count} missing tags"
            )
            if relation_count > 0:
                output_callback(f"Processed {relation_count} relations")

        return reserves

    def extract(
        self,
        bbox: Optional[tuple[float, float, float, float]] = None,
        tags: Optional[List[tuple[str, str]]] = None,
        output_callback: Optional[Callable[[str], None]] = None,
    ) -> List[Dict[str, Any]]:
        query = self.build_query(bbox, tags)
        data = self.query_overpass(query, output_callback=output_callback)

        if output_callback:
            elements_count = len(data.get("elements", []))
            output_callback(f"Received {elements_count} elements from Overpass API")

        reserves = self.parse_elements(data, output_callback=output_callback)

        if output_callback:
            output_callback(f"Parsed {len(reserves)} nature reserves from elements")

        return reserves
