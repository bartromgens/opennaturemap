from rest_framework import viewsets, filters
from django_filters.rest_framework import DjangoFilterBackend
from .models import NatureReserve
from .serializers import (
    NatureReserveGeoJSONSerializer,
    NatureReserveSerializer,
)


class NatureReserveViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = NatureReserve.objects.all()
    serializer_class = NatureReserveSerializer
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["area_type", "operators"]
    search_fields = ["name", "tags"]
    ordering_fields = ["name", "created_at", "updated_at"]
    ordering = ["name"]

    def get_serializer_class(self):
        if (
            self.action == "list"
            and self.request.query_params.get("format") == "geojson"
        ):
            return NatureReserveGeoJSONSerializer
        return NatureReserveSerializer
