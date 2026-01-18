from rest_framework import serializers
import osm2geojson
from .models import NatureReserve


class NatureReserveSerializer(serializers.ModelSerializer):
    geometry = serializers.SerializerMethodField()

    class Meta:
        model = NatureReserve
        fields = [
            "id",
            "name",
            "geometry",
            "tags",
            "area_type",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def get_geometry(self, obj) -> dict:
        osm_element = obj.osm_data
        geojson_data = osm2geojson.json2geojson(
            {"elements": [osm_element]}, filter_used_refs=True
        )
        features = geojson_data.get("features", [])
        if features:
            return features[0].get("geometry")
        return None


class NatureReserveGeoJSONSerializer(serializers.Serializer):
    type = serializers.CharField(default="Feature")
    id = serializers.CharField()
    properties = serializers.DictField()
    geometry = serializers.DictField()

    def to_representation(self, instance):
        serializer = NatureReserveSerializer(instance)
        data = serializer.data
        return {
            "type": "Feature",
            "id": data["id"],
            "properties": {
                "name": data["name"],
                "area_type": data["area_type"],
                **data["tags"],
            },
            "geometry": data["geometry"],
        }
