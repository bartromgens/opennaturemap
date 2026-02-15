import logging

from django.db.models import Count
from rest_framework import viewsets, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

from .geometry_utils import (
    geometry_from_osm_element,
    geojson_geometry_area,
    point_in_geojson_geometry,
)
from .models import NatureReserve, Operator
from .serializers import (
    NatureReserveDetailSerializer,
    NatureReserveGeoJSONSerializer,
    NatureReserveListItemAtPointSerializer,
    NatureReserveSerializer,
    OperatorSerializer,
)

logger = logging.getLogger(__name__)


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
        if self.action == "at_point":
            return NatureReserveListItemAtPointSerializer
        if (
            self.action == "list"
            and self.request.query_params.get("format") == "geojson"
        ):
            return NatureReserveGeoJSONSerializer
        return NatureReserveSerializer

    @action(detail=False, url_path="at_point", methods=["get"])
    def at_point(self, request):
        lat_param = request.query_params.get("lat")
        lon_param = request.query_params.get("lon")
        if lat_param is None or lon_param is None:
            return Response(
                {"error": "Query parameters 'lat' and 'lon' are required"},
                status=400,
            )
        try:
            lat = float(lat_param)
            lon = float(lon_param)
        except ValueError:
            return Response(
                {"error": "lat and lon must be numbers"},
                status=400,
            )
        logger.info("at_point request lat=%.6f lon=%.6f", lat, lon)
        at_point_fields = ["id", "name", "area_type", "osm_data"]
        qs = NatureReserve.objects.filter(
            min_lat__isnull=False,
            max_lat__isnull=False,
            min_lon__isnull=False,
            max_lon__isnull=False,
            min_lat__lte=lat,
            max_lat__gte=lat,
            min_lon__lte=lon,
            max_lon__gte=lon,
        ).only(*at_point_fields)
        reserves_bbox = list(qs)
        logger.info(
            "at_point bbox query: reserves_in_bbox=%d (ids=%s)",
            len(reserves_bbox),
            [r.id for r in reserves_bbox[:10]]
            + (["..."] if len(reserves_bbox) > 10 else []),
        )
        containing: list[tuple[NatureReserve, dict]] = []
        no_geom = 0
        geom_not_containing = 0
        for reserve in reserves_bbox:
            geom = geometry_from_osm_element(reserve.osm_data)
            if geom is None:
                no_geom += 1
                logger.debug(
                    "at_point reserve %s: no geometry from osm_data",
                    reserve.id,
                )
                continue
            if point_in_geojson_geometry(lon, lat, geom):
                containing.append((reserve, geom))
            else:
                geom_not_containing += 1
        logger.info(
            "at_point primary: no_geom=%d geom_not_containing=%d containing=%d",
            no_geom,
            geom_not_containing,
            len(containing),
        )
        containing.sort(key=lambda pair: geojson_geometry_area(pair[1]))
        reserves = [reserve for reserve, _ in containing]
        logger.info(
            "at_point response: result_count=%d ids=%s",
            len(reserves),
            [r.id for r in reserves],
        )
        serializer = NatureReserveListItemAtPointSerializer(reserves, many=True)
        return Response(serializer.data)
