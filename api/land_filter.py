import json
import os
from typing import Optional

import requests
from shapely.geometry import box, shape
from shapely.strtree import STRtree

LAND_GEOJSON_URL = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_110m_land.geojson"
DEFAULT_CACHE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "data", "ne_110m_land.geojson"
)


class LandFilter:
    def __init__(self, cache_path: str = DEFAULT_CACHE_PATH):
        self._cache_path = cache_path
        geojson = self._load_geojson()
        polygons = [
            shape(feature["geometry"])
            for feature in geojson["features"]
            if feature.get("geometry")
        ]
        self._tree = STRtree(polygons)

    def _load_geojson(self) -> dict:
        if not os.path.exists(self._cache_path):
            self._download_geojson()
        with open(self._cache_path, encoding="utf-8") as f:
            return json.load(f)

    def _download_geojson(self) -> None:
        os.makedirs(os.path.dirname(self._cache_path), exist_ok=True)
        response = requests.get(LAND_GEOJSON_URL, timeout=60)
        response.raise_for_status()
        with open(self._cache_path, "w", encoding="utf-8") as f:
            f.write(response.text)

    def tile_intersects_land(
        self, min_lon: float, min_lat: float, max_lon: float, max_lat: float
    ) -> bool:
        tile = box(min_lon, min_lat, max_lon, max_lat)
        return len(self._tree.query(tile)) > 0


_land_filter: Optional[LandFilter] = None


def get_land_filter(cache_path: str = DEFAULT_CACHE_PATH) -> LandFilter:
    global _land_filter
    if _land_filter is None:
        _land_filter = LandFilter(cache_path)
    return _land_filter
