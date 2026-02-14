from rest_framework import serializers

from .geometry_utils import geometry_from_osm_element
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


class NatureReserveDetailSerializer(serializers.ModelSerializer):
    operators = OperatorSerializer(many=True, read_only=True)
    geometry = serializers.SerializerMethodField()

    class Meta:
        model = NatureReserve
        fields = [
            "id",
            "name",
            "tags",
            "area_type",
            "operators",
            "geometry",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def get_geometry(self, obj: NatureReserve) -> dict | None:
        return geometry_from_osm_element(obj.osm_data)


class NatureReserveListItemAtPointSerializer(serializers.ModelSerializer):
    class Meta:
        model = NatureReserve
        fields = ["id", "name", "area_type"]


class NatureReserveGeoJSONSerializer(serializers.Serializer):
    type = serializers.CharField(default="Feature")
    id = serializers.CharField()
    properties = serializers.DictField()
    geometry = serializers.DictField()

    def to_representation(self, instance):
        serializer = NatureReserveSerializer(instance)
        data = serializer.data
        geometry = geometry_from_osm_element(instance.osm_data)
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
