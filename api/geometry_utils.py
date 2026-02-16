from typing import Any

import osm2geojson


def _ring_area_deg2(ring: list[list[float]]) -> float:
    """Planar area of closed ring in degree² (for ordering)."""
    if len(ring) < 3:
        return 0.0
    n = len(ring)
    area = 0.0
    for i in range(n):
        j = (i + 1) % n
        area += ring[i][0] * ring[j][1]
        area -= ring[j][0] * ring[i][1]
    return abs(area) / 2.0


def geojson_geometry_area(geom: dict[str, Any]) -> float:
    """Area in deg² for Polygon/MultiPolygon (ordering)."""
    if not isinstance(geom, dict):
        return 0.0
    gtype = geom.get("type")
    coords = geom.get("coordinates")
    if not coords:
        return 0.0
    if gtype == "Polygon":
        # First ring is exterior; others are holes (subtract).
        total = _ring_area_deg2(coords[0])
        for ring in coords[1:]:
            total -= _ring_area_deg2(ring)
        return max(0.0, total)
    if gtype == "MultiPolygon":
        total = 0.0
        for poly in coords:
            total += _ring_area_deg2(poly[0])
            for ring in poly[1:]:
                total -= _ring_area_deg2(ring)
        return max(0.0, total)
    return 0.0


def _point_in_ring(lon: float, lat: float, ring: list[list[float]]) -> bool:
    """Ray casting: point inside closed ring (odd number of crossings)."""
    n = len(ring)
    if n < 3:
        return False
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if ((yi > lat) != (yj > lat)) and (
            lon < (xj - xi) * (lat - yi) / (yj - yi) + xi
        ):
            inside = not inside
        j = i
    return inside


def point_in_geojson_geometry(lon: float, lat: float, geom: dict[str, Any]) -> bool:
    """True if (lon, lat) is inside the geometry."""
    if not isinstance(geom, dict):
        return False
    gtype = geom.get("type")
    coords = geom.get("coordinates")
    if not coords:
        return False
    if gtype == "Polygon":
        if not _point_in_ring(lon, lat, coords[0]):
            return False
        for ring in coords[1:]:
            if _point_in_ring(lon, lat, ring):
                return False
        return True
    if gtype == "MultiPolygon":
        for poly in coords:
            if not _point_in_ring(lon, lat, poly[0]):
                continue
            inside = True
            for ring in poly[1:]:
                if _point_in_ring(lon, lat, ring):
                    inside = False
                    break
            if inside:
                return True
        return False
    return False


def _points_ring_to_geojson_ring(raw: list[Any]) -> list[list[float]] | None:
    """Single ring (list of {lat,lon} or [lon,lat]) to GeoJSON ring."""
    if not raw or len(raw) < 3:
        return None
    ring: list[list[float]] = []
    for pt in raw:
        if isinstance(pt, (list, tuple)) and len(pt) >= 2:
            ring.append([float(pt[0]), float(pt[1])])
        elif isinstance(pt, dict):
            lon_val = pt.get("lon") if "lon" in pt else pt.get("x")
            lat_val = pt.get("lat") if "lat" in pt else pt.get("y")
            if lon_val is not None and lat_val is not None:
                ring.append([float(lon_val), float(lat_val)])
    if len(ring) < 3:
        return None
    if ring[0] != ring[-1]:
        ring.append(ring[0][:])
    return ring


def _overpass_geometry_to_geojson(raw: list[Any]) -> dict | None:
    """Convert Overpass-style geometry to GeoJSON Polygon."""
    if not raw:
        return None
    first = raw[0]
    if isinstance(first, (list, tuple)) and len(first) > 0:
        inner = first[0]
        if isinstance(inner, (list, tuple)) and len(inner) >= 2:
            pass
        elif isinstance(inner, dict) or (
            isinstance(inner, (list, tuple)) and len(inner) >= 2
        ):
            pass
        else:
            return None
        rings = [_points_ring_to_geojson_ring(r) for r in raw]
        rings = [r for r in rings if r is not None]
        if not rings:
            return None
        return {"type": "Polygon", "coordinates": rings}
    ring = _points_ring_to_geojson_ring(raw)
    if ring is None:
        return None
    return {"type": "Polygon", "coordinates": [ring]}


def reserve_geojson_features(
    osm_data: dict,
    reserve_id: str,
    name: str | None,
    area_type: str,
    operator_ids: list[int],
    tags: dict,
    protect_class: str | None,
) -> list[dict]:
    """Build GeoJSON Feature dicts for a reserve (same structure as export). Returns [] if no geometry."""
    raw_features = osm_element_to_geojson_features(osm_data or {})
    result: list[dict] = []
    osm_type = (
        osm_data.get("type") if isinstance(osm_data, dict) else None
    ) or reserve_id.split("_")[0]
    for feature in raw_features:
        if not isinstance(feature, dict) or feature.get("type") != "Feature":
            continue
        props = dict(tags) if tags else {}
        props["id"] = reserve_id
        props["osm_type"] = osm_type
        props["name"] = name or ""
        props["area_type"] = area_type
        props["operator_ids"] = ",".join(str(i) for i in operator_ids)
        if protect_class:
            props["protect_class"] = protect_class
        result.append(
            {
                "type": "Feature",
                "id": reserve_id,
                "geometry": feature.get("geometry"),
                "properties": props,
            }
        )
    return result


def geometry_from_osm_element(osm_data: dict) -> dict | None:
    """First GeoJSON geometry from OSM element, or None."""
    features = osm_element_to_geojson_features(osm_data)
    for feature in features:
        g = feature.get("geometry")
        if g and g.get("type") and g.get("coordinates"):
            return g
    raw_geom = osm_data.get("geometry") if isinstance(osm_data, dict) else None
    if isinstance(raw_geom, list):
        return _overpass_geometry_to_geojson(raw_geom)
    return None


def osm_element_to_geojson_features(osm_data: dict) -> list[dict]:
    """GeoJSON Feature dicts from one OSM element, or []."""
    try:
        result = osm2geojson.json2geojson({"elements": [osm_data]})
        if isinstance(result, dict) and result.get("features"):
            features = result["features"]
        elif isinstance(result, list):
            features = result
        else:
            return []
        return [
            f for f in features if isinstance(f, dict) and f.get("type") == "Feature"
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


def _points_to_lonlats(raw: list[Any]) -> tuple[list[float], list[float]]:
    """Lons and lats from list of points (Overpass or GeoJSON)."""
    lons: list[float] = []
    lats: list[float] = []
    for pt in raw:
        if isinstance(pt, (list, tuple)) and len(pt) >= 2:
            lons.append(float(pt[0]))
            lats.append(float(pt[1]))
        elif isinstance(pt, dict):
            lon_val = pt.get("lon") if "lon" in pt else pt.get("x")
            lat_val = pt.get("lat") if "lat" in pt else pt.get("y")
            if lon_val is not None and lat_val is not None:
                lons.append(float(lon_val))
                lats.append(float(lat_val))
    return (lons, lats)


def bbox_from_osm_geometry(
    raw: Any,
) -> tuple[float, float, float, float] | None:
    if raw is None:
        return None
    if isinstance(raw, dict) and raw.get("type") in (
        "Polygon",
        "MultiPolygon",
    ):
        return bbox_from_geojson_geometry(raw)
    if isinstance(raw, list):
        if not raw:
            return None
        first = raw[0]
        if isinstance(first, (list, tuple)):
            bboxes = [bbox_from_osm_geometry(item) for item in raw]
            bboxes = [b for b in bboxes if b is not None]
            if not bboxes:
                return None
            return (
                min(b[0] for b in bboxes),
                min(b[1] for b in bboxes),
                max(b[2] for b in bboxes),
                max(b[3] for b in bboxes),
            )
        if len(raw) >= 3:
            lons, lats = _points_to_lonlats(raw)
            if lons and lats:
                return (min(lons), min(lats), max(lons), max(lats))
    return None


def bbox_from_osm_element(
    elem: dict[str, Any],
) -> tuple[float, float, float, float] | None:
    """Bbox from a stored OSM element (way/relation). Uses bounds, geometry, or members."""
    if not isinstance(elem, dict):
        return None
    bounds = elem.get("bounds")
    if isinstance(bounds, dict):
        minlon = bounds.get("minlon")
        minlat = bounds.get("minlat")
        maxlon = bounds.get("maxlon")
        maxlat = bounds.get("maxlat")
        if all(x is not None for x in (minlon, minlat, maxlon, maxlat)):
            return (float(minlon), float(minlat), float(maxlon), float(maxlat))
    geometry = elem.get("geometry")
    if geometry is not None:
        bbox = bbox_from_osm_geometry(geometry)
        if bbox is not None:
            return bbox
    members = elem.get("members")
    if isinstance(members, list):
        bboxes: list[tuple[float, float, float, float]] = []
        for m in members:
            if not isinstance(m, dict):
                continue
            geom = m.get("geometry")
            if geom is not None:
                b = bbox_from_osm_geometry(geom)
                if b is not None:
                    bboxes.append(b)
        if bboxes:
            return (
                min(b[0] for b in bboxes),
                min(b[1] for b in bboxes),
                max(b[2] for b in bboxes),
                max(b[3] for b in bboxes),
            )
    return None
