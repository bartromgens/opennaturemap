from typing import Any

import osm2geojson


def osm_element_to_geojson_features(osm_data: dict) -> list[dict]:
    """Return list of GeoJSON Feature dicts from one OSM element, or [] on failure."""
    try:
        result = osm2geojson.json2geojson({"elements": [osm_data]})
        if isinstance(result, dict) and result.get("features"):
            features = result["features"]
        elif isinstance(result, list):
            features = result
        else:
            return []
        return [
            f
            for f in features
            if isinstance(f, dict) and f.get("type") == "Feature"
        ]
    except Exception:
        return []


def bbox_from_geojson_geometry(
    geom: dict[str, Any],
) -> tuple[float, float, float, float] | None:
    if not isinstance(geom, dict):
        return None
    coords = geom.get("coordinates")
    if coords is None:
        return None
    lons: list[float] = []
    lats: list[float] = []

    def flatten(c: Any) -> None:
        if isinstance(c, (int, float)):
            return
        if isinstance(c, list):
            if (
                len(c) >= 2
                and isinstance(c[0], (int, float))
                and isinstance(c[1], (int, float))
            ):
                lons.append(float(c[0]))
                lats.append(float(c[1]))
            else:
                for item in c:
                    flatten(item)

    flatten(coords)
    if not lons or not lats:
        return None
    return (min(lons), min(lats), max(lons), max(lats))


def bbox_from_osm_geometry(raw: Any) -> tuple[float, float, float, float] | None:
    if raw is None:
        return None
    if isinstance(raw, dict) and raw.get("type") in (
        "Polygon",
        "MultiPolygon",
    ):
        return bbox_from_geojson_geometry(raw)
    if isinstance(raw, list) and len(raw) >= 3:
        lons = []
        lats = []
        for pt in raw:
            if isinstance(pt, (list, tuple)) and len(pt) >= 2:
                lons.append(float(pt[0]))
                lats.append(float(pt[1]))
        if lons and lats:
            return (min(lons), min(lats), max(lons), max(lats))
    return None
