from rest_framework import serializers
from .models import NatureReserve


class NatureReserveSerializer(serializers.ModelSerializer):
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
