import requests
import time
import random
from typing import List, Dict, Any, Optional, Callable

USER_AGENT = "OpenNatureMap/1.0 (https://github.com/bartromgens/opennaturemap; contact@example.com)"


class ServerManager:
    DEFAULT_SERVERS = [
        "https://overpass-api.de/api/interpreter",  # Germany
        "https://osm.hpi.de/overpass/api/interpreter",  # Germany (Potsdam)
        "https://overpass.private.coffee/api/interpreter",  # Austria
        "https://z.overpass-api.de/api/interpreter",
        "https://overpass.kumi.systems/api/interpreter",
        "https://lz4.overpass-api.de/api/interpreter",
    ]

    def __init__(
        self,
        servers: Optional[List[str]] = None,
        max_consecutive_failures: int = 3,
        requests_before_retry_failed: int = 50,
    ):
        self.servers = servers if servers is not None else self.DEFAULT_SERVERS
        self.max_consecutive_failures = max_consecutive_failures
        self.requests_before_retry_failed = requests_before_retry_failed
        self._server_index = 0
        self._server_failures: Dict[str, int] = {}
        self._successful_requests_since_skip: int = 0

    def get_servers_for_query(
        self, output_callback: Optional[Callable[[str], None]] = None
    ) -> List[str]:
        # Rotate through servers: start with a different server for each query
        rotated_servers = (
            self.servers[self._server_index :] + self.servers[: self._server_index]
        )
        self._server_index = (self._server_index + 1) % len(self.servers)

        # Filter out servers that have failed too many times
        skipped_servers = [
            s
            for s in rotated_servers
            if self._server_failures.get(s, 0) >= self.max_consecutive_failures
        ]
        available_servers = [
            s
            for s in rotated_servers
            if self._server_failures.get(s, 0) < self.max_consecutive_failures
        ]

        if skipped_servers and output_callback:
            output_callback(
                f"Skipping {len(skipped_servers)} server(s) due to consistent failures: {', '.join(skipped_servers)}"
            )

        # If all servers are filtered out, reset failures and try all servers
        if not available_servers:
            if output_callback:
                output_callback(
                    "All servers have failed consistently, resetting and trying all servers again..."
                )
            self._server_failures.clear()
            available_servers = rotated_servers

        return available_servers

    def record_failure(self, server_url: str) -> None:
        self._server_failures[server_url] = self._server_failures.get(server_url, 0) + 1

    def record_success(self, server_url: str) -> None:
        self._server_failures[server_url] = 0
        self._successful_requests_since_skip += 1
        if self._successful_requests_since_skip >= self.requests_before_retry_failed:
            self._server_failures.clear()
            self._successful_requests_since_skip = 0


class OSMNatureReserveExtractor:
    def __init__(
        self,
        overpass_url: str = "https://overpass-api.de/api/interpreter",
        user_agent: Optional[str] = None,
    ):
        self.overpass_url = overpass_url
        self.server_manager = ServerManager()
        self.timeout = 180
        self.max_retries = 3
        self.user_agent = user_agent or USER_AGENT
        self.base_delay = 1.0
        self.max_delay = 300.0

    def build_query(
        self,
        bbox: Optional[tuple[float, float, float, float]] = None,
        tags: Optional[List[tuple[str, str]]] = None,
        area_iso: Optional[str] = None,
    ) -> str:
        if tags is None:
            tags = [
                ("leisure", "nature_reserve"),
                ("boundary", "protected_area"),
                ("boundary", "national_park"),
                ("landuse", "conservation"),
            ]

        bbox_filter = ""
        if bbox:
            min_lon, min_lat, max_lon, max_lat = bbox
            bbox_filter = f"({min_lat},{min_lon},{max_lat},{max_lon})"

        area_filter = ""
        if area_iso:
            area_filter = "(area.searchArea)"

        query_parts = []
        for key, value in tags:
            if bbox:
                query_parts.append(
                    f'  way["{key}"="{value}"]{area_filter}{bbox_filter};'
                )
                query_parts.append(
                    f'  relation["{key}"="{value}"]{area_filter}{bbox_filter};'
                )
            else:
                query_parts.append(f'  way["{key}"="{value}"]{area_filter};')
                query_parts.append(f'  relation["{key}"="{value}"]{area_filter};')

        query_timeout = min(self.timeout, 90)
        area_line = ""
        if area_iso:
            area_line = f'area["ISO3166-1"="{area_iso}"]->.searchArea;\n'
        query = f"""[out:json][timeout:{query_timeout}];
{area_line}(
{chr(10).join(query_parts)}
);
out geom;"""
        return query

    def query_overpass(
        self, query: str, output_callback: Optional[Callable[[str], None]] = None
    ) -> Dict[str, Any]:
        if output_callback is None:
            output_callback = print

        servers_to_try = self.server_manager.get_servers_for_query(output_callback)

        for attempt in range(self.max_retries):
            for idx, server_url in enumerate(servers_to_try):
                try:
                    if attempt > 0:
                        wait_time = self._calculate_backoff(attempt)
                        output_callback(
                            f"Retrying in {wait_time:.1f} seconds... (attempt {attempt + 1}/{self.max_retries})"
                        )
                        time.sleep(wait_time)
                    elif idx > 0:
                        time.sleep(0.5)

                    output_callback(f"Querying Overpass API: {server_url}")
                    headers = {"User-Agent": self.user_agent}
                    response = requests.post(
                        server_url,
                        data={"data": query},
                        headers=headers,
                        timeout=self.timeout + 30,
                    )

                    if response.status_code == 200:
                        try:
                            data = response.json()
                            if not data or "elements" not in data:
                                output_callback(
                                    f"Empty or invalid response from {server_url}, trying next server..."
                                )
                                self.server_manager.record_failure(server_url)
                                continue
                            # Success: reset failure count for this server
                            self.server_manager.record_success(server_url)
                            return data
                        except ValueError as e:
                            output_callback(
                                f"Invalid JSON response from {server_url}: {e}, trying next server..."
                            )
                            self.server_manager.record_failure(server_url)
                            continue
                    elif response.status_code == 504:
                        output_callback(
                            f"Server timeout (504) from {server_url}, trying next server..."
                        )
                        self.server_manager.record_failure(server_url)
                        continue
                    elif response.status_code == 429:
                        output_callback(
                            f"Rate limited (429) from {server_url}, waiting 10 seconds before trying next server..."
                        )
                        time.sleep(10)
                        # Record failure so we try other servers first
                        self.server_manager.record_failure(server_url)
                        continue
                    elif response.status_code == 503:
                        output_callback(
                            f"Service unavailable (503) from {server_url}, waiting 10 seconds before trying next server..."
                        )
                        time.sleep(10)
                        # Record failure so we try other servers first
                        self.server_manager.record_failure(server_url)
                        continue
                    else:
                        error_msg = (
                            f"HTTP {response.status_code}: {response.text[:500]}"
                        )
                        if response.status_code == 400:
                            error_msg += f"\n\nQuery that failed:\n{query}"
                        self.server_manager.record_failure(server_url)
                        if (
                            attempt == self.max_retries - 1
                            and server_url == servers_to_try[-1]
                        ):
                            raise requests.exceptions.HTTPError(error_msg)
                        output_callback(
                            f"HTTP error from {server_url}: {error_msg}, trying next server..."
                        )
                        continue

                except requests.exceptions.Timeout:
                    output_callback(
                        f"Request timeout from {server_url}, trying next server..."
                    )
                    self.server_manager.record_failure(server_url)
                    continue
                except requests.exceptions.RequestException as e:
                    if (
                        attempt == self.max_retries - 1
                        and server_url == servers_to_try[-1]
                    ):
                        self.server_manager.record_failure(server_url)
                        raise
                    output_callback(
                        f"Request error from {server_url}: {e}, trying next server..."
                    )
                    self.server_manager.record_failure(server_url)
                    continue

        raise requests.exceptions.RequestException(
            f"Failed to query Overpass API after {self.max_retries} attempts across {len(servers_to_try)} servers"
        )

    def _calculate_backoff(self, attempt: int) -> float:
        """Calculate exponential backoff with jitter."""
        exponential_delay = min(self.base_delay * (2**attempt), self.max_delay)
        jitter = random.uniform(0, exponential_delay * 0.1)
        return exponential_delay + jitter

    def _get_retry_after(self, response: requests.Response, default: float) -> float:
        """Extract Retry-After header value or use default."""
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                return float(retry_after)
            except ValueError:
                pass
        return default

    def determine_area_type(self, tags: Dict[str, str]) -> str:
        if tags.get("leisure") == "nature_reserve":
            return "nature_reserve"
        elif tags.get("boundary") == "national_park":
            protect_class = tags.get("protect_class", "unknown")
            return f"national_park_class_{protect_class}"
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
        members = relation.get("members", [])
        if not members:
            return None

        # Fallback: build a map of way IDs to their geometries from separate
        # way elements (present when the query uses `(._;>;)`).
        way_geometries: Dict[int, list] = {}
        for elem in all_elements:
            if elem.get("type") == "way" and "geometry" in elem:
                way_id = elem.get("id")
                if way_id is not None:
                    way_geometries[int(way_id)] = elem.get("geometry", [])

        # Collect outer and inner rings
        outer_rings: List[List[Dict[str, float]]] = []
        inner_rings: List[List[Dict[str, float]]] = []
        missing_ways: List[int] = []

        for member in members:
            if member.get("type") != "way":
                continue

            way_ref = member.get("ref")
            if way_ref is None:
                continue

            # `out geom` embeds geometry directly in the member; fall back to
            # looking up the way as a separate element in `all_elements`.
            way_geom = member.get("geometry") or way_geometries.get(int(way_ref))
            if not way_geom:
                missing_ways.append(int(way_ref))
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
            if elem_type == "relation":
                relation_count += 1
                if geometry is None or (
                    isinstance(geometry, list) and len(geometry) == 0
                ):
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
        area_iso: Optional[str] = None,
        output_callback: Optional[Callable[[str], None]] = None,
    ) -> List[Dict[str, Any]]:
        query = self.build_query(bbox, tags, area_iso=area_iso)
        data = self.query_overpass(query, output_callback=output_callback)

        if output_callback:
            elements_count = len(data.get("elements", []))
            output_callback(f"Received {elements_count} elements from Overpass API")

        reserves = self.parse_elements(data, output_callback=output_callback)

        if output_callback:
            output_callback(f"Parsed {len(reserves)} nature reserves from elements")

        return reserves
