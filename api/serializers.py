from rest_framework import serializers
from .models import NatureReserve, Operator


class OperatorSerializer(serializers.ModelSerializer):
    reserve_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Operator
        fields = ["id", "name", "reserve_count"]


class NatureReserveSerializer(serializers.ModelSerializer):
    class Meta:
        model = NatureReserve
        fields = [
            "id",
            "name",
            "tags",
            "area_type",
            "operators",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]


def _osm_geometry_to_geojson(osm_data: dict) -> dict | None:
    if not isinstance(osm_data, dict):
        return None
    raw = osm_data.get("geometry")
    if raw is None:
        return None
    if isinstance(raw, dict) and raw.get("type") in ("Polygon", "MultiPolygon"):
        return raw
    if not isinstance(raw, list) or len(raw) < 3:
        return None
    ring = list(raw)
    if ring[0] != ring[-1]:
        ring.append(ring[0])
    return {"type": "Polygon", "coordinates": [ring]}


class NatureReserveGeoJSONSerializer(serializers.Serializer):
    type = serializers.CharField(default="Feature")
    id = serializers.CharField()
    properties = serializers.DictField()
    geometry = serializers.DictField()

    def to_representation(self, instance):
        serializer = NatureReserveSerializer(instance)
        data = serializer.data
        geometry = _osm_geometry_to_geojson(instance.osm_data)
        return {
            "type": "Feature",
            "id": data["id"],
            "properties": {
                "name": data["name"],
                "area_type": data["area_type"],
                **data["tags"],
            },
            "geometry": geometry,
        }
