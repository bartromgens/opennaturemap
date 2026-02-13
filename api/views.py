from django.db.models import Count
from rest_framework import viewsets, filters
from django_filters.rest_framework import DjangoFilterBackend

from .models import NatureReserve, Operator
from .serializers import (
    NatureReserveDetailSerializer,
    NatureReserveGeoJSONSerializer,
    NatureReserveSerializer,
    OperatorSerializer,
)


class OperatorViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Operator.objects.annotate(
        reserve_count=Count("nature_reserves")
    ).order_by("-reserve_count", "name")
    serializer_class = OperatorSerializer


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

    def get_queryset(self):
        qs = super().get_queryset()
        min_lat = self.request.query_params.get("min_lat")
        min_lon = self.request.query_params.get("min_lon")
        max_lat = self.request.query_params.get("max_lat")
        max_lon = self.request.query_params.get("max_lon")
        if (
            min_lat is not None
            and min_lon is not None
            and max_lat is not None
            and max_lon is not None
        ):
            try:
                min_lat_f = float(min_lat)
                min_lon_f = float(min_lon)
                max_lat_f = float(max_lat)
                max_lon_f = float(max_lon)
                qs = qs.filter(
                    min_lon__isnull=False,
                    max_lon__isnull=False,
                    min_lat__isnull=False,
                    max_lat__isnull=False,
                    min_lon__lte=max_lon_f,
                    max_lon__gte=min_lon_f,
                    min_lat__lte=max_lat_f,
                    max_lat__gte=min_lat_f,
                )
            except ValueError:
                pass
        return qs

    def get_serializer_class(self):
        if self.action == "retrieve":
            return NatureReserveDetailSerializer
        if (
            self.action == "list"
            and self.request.query_params.get("format") == "geojson"
        ):
            return NatureReserveGeoJSONSerializer
        return NatureReserveSerializer
