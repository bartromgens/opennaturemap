from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.core.management import call_command
from io import StringIO
from api.models import NatureReserve, Operator
from api.geometry_utils import (
    bbox_from_osm_element,
    bbox_from_osm_geometry,
    geometry_from_osm_element,
    point_in_geojson_geometry,
)
import json


class BboxFromOsmTest(TestCase):
    def test_bbox_from_osm_geometry_none_returns_none(self):
        self.assertIsNone(bbox_from_osm_geometry(None))

    def test_bbox_from_osm_geometry_empty_list_returns_none(self):
        self.assertIsNone(bbox_from_osm_geometry([]))

    def test_bbox_from_osm_geometry_single_ring_dict_points(self):
        geometry = [
            {"lon": 5.19, "lat": 52.09},
            {"lon": 5.21, "lat": 52.09},
            {"lon": 5.21, "lat": 52.11},
            {"lon": 5.19, "lat": 52.11},
            {"lon": 5.19, "lat": 52.09},
        ]
        self.assertEqual(
            bbox_from_osm_geometry(geometry),
            (5.19, 52.09, 5.21, 52.11),
        )

    def test_bbox_from_osm_geometry_multipolygon_list_of_rings(self):
        ring1 = [
            {"lon": -8.637, "lat": 42.394},
            {"lon": -8.630, "lat": 42.394},
            {"lon": -8.630, "lat": 42.419},
            {"lon": -8.637, "lat": 42.394},
        ]
        ring2 = [
            {"lon": -8.64, "lat": 42.40},
            {"lon": -8.63, "lat": 42.40},
            {"lon": -8.63, "lat": 42.41},
            {"lon": -8.64, "lat": 42.40},
        ]
        self.assertEqual(
            bbox_from_osm_geometry([ring1, ring2]),
            (-8.64, 42.394, -8.63, 42.419),
        )

    def test_bbox_from_osm_element_bounds(self):
        elem = {
            "type": "relation",
            "id": 13081016,
            "bounds": {
                "minlat": 42.3944393,
                "minlon": -8.6376998,
                "maxlat": 42.4188695,
                "maxlon": -8.6303364,
            },
        }
        self.assertEqual(
            bbox_from_osm_element(elem),
            (-8.6376998, 42.3944393, -8.6303364, 42.4188695),
        )

    def test_bbox_from_osm_element_geometry(self):
        elem = {
            "type": "way",
            "id": 123,
            "geometry": [
                {"lon": 5.2, "lat": 52.1},
                {"lon": 5.3, "lat": 52.1},
                {"lon": 5.3, "lat": 52.2},
                {"lon": 5.2, "lat": 52.2},
                {"lon": 5.2, "lat": 52.1},
            ],
        }
        self.assertEqual(
            bbox_from_osm_element(elem),
            (5.2, 52.1, 5.3, 52.2),
        )

    def test_bbox_from_osm_element_members_with_geometry(self):
        elem = {
            "type": "relation",
            "id": 13081016,
            "members": [
                {
                    "type": "way",
                    "ref": 874404092,
                    "role": "outer",
                    "geometry": [
                        {"lat": 42.418, "lon": -8.636},
                        {"lat": 42.417, "lon": -8.636},
                        {"lat": 42.417, "lon": -8.635},
                        {"lat": 42.418, "lon": -8.636},
                    ],
                },
                {
                    "type": "way",
                    "ref": 972474940,
                    "role": "outer",
                    "geometry": [
                        {"lat": 42.419, "lon": -8.637},
                        {"lat": 42.418, "lon": -8.637},
                        {"lat": 42.418, "lon": -8.636},
                        {"lat": 42.419, "lon": -8.637},
                    ],
                },
            ],
        }
        self.assertEqual(
            bbox_from_osm_element(elem),
            (-8.637, 42.417, -8.635, 42.419),
        )

    def test_bbox_from_osm_element_prefers_bounds_over_geometry(self):
        elem = {
            "bounds": {
                "minlon": 1.0,
                "minlat": 2.0,
                "maxlon": 3.0,
                "maxlat": 4.0,
            },
            "geometry": [
                {"lon": 9.0, "lat": 9.0},
                {"lon": 10.0, "lat": 10.0},
                {"lon": 10.0, "lat": 9.0},
            ],
        }
        self.assertEqual(bbox_from_osm_element(elem), (1.0, 2.0, 3.0, 4.0))

    def test_bbox_from_osm_element_no_geometry_returns_none(self):
        self.assertIsNone(bbox_from_osm_element({}))
        self.assertIsNone(bbox_from_osm_element({"type": "relation", "id": 1}))

    def test_bbox_from_osm_element_not_dict_returns_none(self):
        self.assertIsNone(bbox_from_osm_element(None))
        self.assertIsNone(bbox_from_osm_element([]))


class ImportNatureReservesTest(TestCase):
    def setUp(self):
        self.test_bbox = (5.14134, 52.07195, 5.28734, 52.16195)
        self.test_coordinate_lat = 52.11695
        self.test_coordinate_lon = 5.21434

    @patch("api.extractors.OSMNatureReserveExtractor.query_overpass")
    def test_import_nature_reserves_small_bbox_utrecht(self, mock_query_overpass):
        mock_response_data = {
            "elements": [
                {
                    "type": "way",
                    "id": 123456,
                    "tags": {
                        "leisure": "nature_reserve",
                        "name": "Test Nature Reserve",
                        "natural": "wood",
                    },
                    "geometry": [
                        {"lat": 52.11695, "lon": 5.21434},
                        {"lat": 52.11700, "lon": 5.21440},
                        {"lat": 52.11690, "lon": 5.21450},
                        {"lat": 52.11695, "lon": 5.21434},
                    ],
                },
                {
                    "type": "relation",
                    "id": 789012,
                    "tags": {
                        "boundary": "protected_area",
                        "protect_class": "4",
                        "name": "Protected Area Test",
                    },
                    "members": [],
                },
            ]
        }

        mock_query_overpass.return_value = mock_response_data

        bbox_str = f"{self.test_bbox[0]},{self.test_bbox[1]},{self.test_bbox[2]},{self.test_bbox[3]}"

        out = StringIO()
        call_command("import_nature_reserves", "--bbox", bbox_str, stdout=out)

        output = out.getvalue()
        self.assertIn("Extracting nature reserves from OpenStreetMap", output)
        self.assertIn("custom bounding box", output)

        mock_query_overpass.assert_called_once()
        call_args = mock_query_overpass.call_args
        self.assertIsNotNone(call_args)

    @patch("api.extractors.OSMNatureReserveExtractor.extract")
    def test_import_nature_reserves_test_region_option(self, mock_extract):
        mock_reserves = [
            {
                "id": "way_123456",
                "name": "Test Nature Reserve",
                "osm_data": {
                    "type": "way",
                    "id": 123456,
                    "tags": {
                        "leisure": "nature_reserve",
                        "name": "Test Nature Reserve",
                    },
                },
                "tags": {"leisure": "nature_reserve", "name": "Test Nature Reserve"},
                "area_type": "nature_reserve",
            },
        ]

        mock_extract.return_value = mock_reserves

        out = StringIO()
        call_command("import_nature_reserves", "--test-region", stdout=out)

        output = out.getvalue()
        self.assertIn("Extracting nature reserves from OpenStreetMap", output)
        self.assertIn("test region (Utrecht, 52.11695/5.21434)", output)

        mock_extract.assert_called_once()
        call_args = mock_extract.call_args
        self.assertIsNotNone(call_args)
        self.assertEqual(call_args.kwargs["bbox"], self.test_bbox)

    @patch("api.extractors.OSMNatureReserveExtractor.extract")
    def test_import_nature_reserves_creates_records(self, mock_extract):
        geometry = [
            {"lon": 5.2, "lat": 52.1},
            {"lon": 5.3, "lat": 52.1},
            {"lon": 5.3, "lat": 52.2},
            {"lon": 5.2, "lat": 52.1},
        ]
        mock_reserves = [
            {
                "id": "way_123456",
                "name": "Test Nature Reserve",
                "osm_data": {
                    "type": "way",
                    "id": 123456,
                    "tags": {
                        "leisure": "nature_reserve",
                        "name": "Test Nature Reserve",
                    },
                    "geometry": geometry,
                },
                "tags": {"leisure": "nature_reserve", "name": "Test Nature Reserve"},
                "area_type": "nature_reserve",
                "geometry": geometry,
            },
            {
                "id": "relation_789012",
                "name": "Protected Area Test",
                "osm_data": {
                    "type": "relation",
                    "id": 789012,
                    "tags": {
                        "boundary": "protected_area",
                        "name": "Protected Area Test",
                    },
                    "geometry": geometry,
                },
                "tags": {"boundary": "protected_area", "name": "Protected Area Test"},
                "area_type": "protected_area_class_4",
                "geometry": geometry,
            },
        ]

        mock_extract.return_value = mock_reserves

        bbox_str = f"{self.test_bbox[0]},{self.test_bbox[1]},{self.test_bbox[2]},{self.test_bbox[3]}"

        out = StringIO()
        call_command("import_nature_reserves", "--bbox", bbox_str, stdout=out)

        self.assertEqual(NatureReserve.objects.count(), 2)

        reserve1 = NatureReserve.objects.get(id="way_123456")
        self.assertEqual(reserve1.name, "Test Nature Reserve")
        self.assertEqual(reserve1.area_type, "nature_reserve")

        reserve2 = NatureReserve.objects.get(id="relation_789012")
        self.assertEqual(reserve2.name, "Protected Area Test")
        self.assertEqual(reserve2.area_type, "protected_area_class_4")

        output = out.getvalue()
        self.assertIn("Found 2 nature reserves", output)
        self.assertIn("Created: 2", output)

    @patch("api.extractors.OSMNatureReserveExtractor.extract")
    def test_import_nature_reserves_updates_existing(self, mock_extract):
        min_lon, min_lat, max_lon, max_lat = self.test_bbox
        NatureReserve.objects.create(
            id="way_123456",
            name="Old Name",
            osm_data={},
            tags={},
            area_type="nature_reserve",
            min_lon=min_lon,
            min_lat=min_lat,
            max_lon=max_lon,
            max_lat=max_lat,
        )

        geometry = [
            {"lon": 5.2, "lat": 52.1},
            {"lon": 5.3, "lat": 52.1},
            {"lon": 5.3, "lat": 52.2},
            {"lon": 5.2, "lat": 52.2},
            {"lon": 5.2, "lat": 52.1},
        ]
        mock_reserves = [
            {
                "id": "way_123456",
                "name": "Updated Name",
                "osm_data": {
                    "type": "way",
                    "id": 123456,
                    "tags": {},
                    "geometry": geometry,
                },
                "tags": {},
                "area_type": "nature_reserve",
                "geometry": geometry,
            },
        ]

        mock_extract.return_value = mock_reserves

        bbox_str = f"{self.test_bbox[0]},{self.test_bbox[1]},{self.test_bbox[2]},{self.test_bbox[3]}"

        out = StringIO()
        call_command("import_nature_reserves", "--bbox", bbox_str, stdout=out)

        self.assertEqual(NatureReserve.objects.count(), 1)
        reserve = NatureReserve.objects.get(id="way_123456")
        self.assertEqual(reserve.name, "Updated Name")

        output = out.getvalue()
        self.assertIn("Updated: 1", output)

    @patch("api.extractors.OSMNatureReserveExtractor.extract")
    def test_import_nature_reserves_clear_option(self, mock_extract):
        min_lon, min_lat, max_lon, max_lat = self.test_bbox
        NatureReserve.objects.create(
            id="way_111",
            name="Old Reserve",
            osm_data={},
            tags={},
            area_type="nature_reserve",
            min_lon=min_lon,
            min_lat=min_lat,
            max_lon=max_lon,
            max_lat=max_lat,
        )

        mock_extract.return_value = []

        bbox_str = f"{self.test_bbox[0]},{self.test_bbox[1]},{self.test_bbox[2]},{self.test_bbox[3]}"

        out = StringIO()
        call_command(
            "import_nature_reserves", "--bbox", bbox_str, "--clear", stdout=out
        )

        self.assertEqual(NatureReserve.objects.count(), 0)

        output = out.getvalue()
        self.assertIn("Cleared 1 existing nature reserves", output)

    @patch("api.extractors.requests.post")
    def test_import_relation_7010743_de_deelen(self, mock_post):
        """Test that relation 7010743 (De Deelen) is imported correctly.

        This relation has both boundary=protected_area and leisure=nature_reserve tags,
        and is a multipolygon relation with member ways that need to be included.

        This test mocks the HTTP request to Overpass API, allowing the full extraction
        pipeline to run including parse_elements and extract_relation_geometry.
        """
        # Coordinates for De Deelen: ~53.0214° N, 5.9044° E
        # Create a small bbox around this location
        de_deelen_bbox = (5.8, 52.95, 6.0, 53.1)

        # Mock Overpass API response with relation 7010743 and its member ways
        mock_response_data = {
            "elements": [
                # The relation itself
                {
                    "type": "relation",
                    "id": 7010743,
                    "tags": {
                        "boundary": "protected_area",
                        "leisure": "nature_reserve",
                        "name": "De Deelen",
                        "protect_class": "97",
                        "protection_title": "Natura 2000-gebied",
                        "type": "multipolygon",
                    },
                    "members": [
                        {"type": "way", "ref": 749016717, "role": "outer"},
                        {"type": "way", "ref": 749016716, "role": "outer"},
                    ],
                    "geometry": [],  # Empty geometry, needs to be extracted from members
                },
                # Member way 749016717
                {
                    "type": "way",
                    "id": 749016717,
                    "geometry": [
                        {"lat": 53.021, "lon": 5.904},
                        {"lat": 53.022, "lon": 5.905},
                        {"lat": 53.023, "lon": 5.904},
                        {"lat": 53.021, "lon": 5.904},
                    ],
                },
                # Member way 749016716
                {
                    "type": "way",
                    "id": 749016716,
                    "geometry": [
                        {"lat": 53.020, "lon": 5.903},
                        {"lat": 53.021, "lon": 5.904},
                        {"lat": 53.020, "lon": 5.905},
                        {"lat": 53.020, "lon": 5.903},
                    ],
                },
            ]
        }

        # Mock the HTTP response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_data
        mock_response.headers = {}
        mock_post.return_value = mock_response

        bbox_str = f"{de_deelen_bbox[0]},{de_deelen_bbox[1]},{de_deelen_bbox[2]},{de_deelen_bbox[3]}"

        out = StringIO()
        call_command("import_nature_reserves", "--bbox", bbox_str, stdout=out)

        # Verify that the HTTP request was made
        self.assertTrue(mock_post.called)
        call_args = mock_post.call_args
        self.assertIsNotNone(call_args)

        # Verify the query includes the relation tags
        query_data = call_args.kwargs.get("data", {}).get("data", "")
        self.assertIn('relation["boundary"="protected_area"]', query_data)
        self.assertIn('relation["leisure"="nature_reserve"]', query_data)

        # Verify that the relation was imported
        self.assertEqual(NatureReserve.objects.count(), 1)

        reserve = NatureReserve.objects.get(id="relation_7010743")
        self.assertEqual(reserve.name, "De Deelen")
        self.assertEqual(
            reserve.area_type, "nature_reserve"
        )  # leisure=nature_reserve takes precedence
        self.assertEqual(reserve.tags["boundary"], "protected_area")
        self.assertEqual(reserve.tags["leisure"], "nature_reserve")
        self.assertEqual(reserve.tags["protect_class"], "97")
        self.assertEqual(reserve.protect_class, "97")
        self.assertIsNotNone(reserve.osm_data)
        self.assertEqual(reserve.osm_data["id"], 7010743)
        self.assertEqual(reserve.osm_data["type"], "relation")
        # Verify that the relation has members (needed for geometry extraction)
        self.assertIn("members", reserve.osm_data)
        self.assertEqual(len(reserve.osm_data["members"]), 2)
        # Verify that geometry was extracted (osm_data should contain the full element)
        # The geometry should be in the reserve data structure, but since it's not
        # stored separately in the model, we verify the relation was processed correctly
        # by checking it was created (which means geometry extraction succeeded)

        output = out.getvalue()
        self.assertIn("Extracting nature reserves from OpenStreetMap", output)
        self.assertIn("Found 1 nature reserves", output)
        self.assertIn("Created: 1", output)


class AtPointTest(TestCase):
    """Tests for the at_point endpoint logic (bbox filter + point-in-geometry)."""

    def setUp(self):
        self.lat = 52.1
        self.lon = 5.2
        self.osm_data_with_geometry = {
            "type": "way",
            "id": 999,
            "tags": {"leisure": "nature_reserve", "name": "AtPoint Test Reserve"},
            "geometry": [
                {"lat": 52.09, "lon": 5.19},
                {"lat": 52.11, "lon": 5.19},
                {"lat": 52.11, "lon": 5.21},
                {"lat": 52.09, "lon": 5.21},
                {"lat": 52.09, "lon": 5.19},
            ],
        }
        self.bbox = (5.19, 52.09, 5.21, 52.11)

    def test_geometry_and_point_in_geometry(self):
        geom = geometry_from_osm_element(self.osm_data_with_geometry)
        self.assertIsNotNone(geom, "geometry_from_osm_element should return a polygon")
        self.assertEqual(geom.get("type"), "Polygon")
        inside = point_in_geojson_geometry(self.lon, self.lat, geom)
        self.assertTrue(inside, "point (5.2, 52.1) should be inside the test polygon")

    def test_at_point_returns_reserve_when_bbox_and_geometry_contain_point(self):
        min_lon, min_lat, max_lon, max_lat = self.bbox
        NatureReserve.objects.create(
            id="way_999",
            name="AtPoint Test Reserve",
            osm_data=self.osm_data_with_geometry,
            tags={"leisure": "nature_reserve"},
            area_type="nature_reserve",
            min_lon=min_lon,
            min_lat=min_lat,
            max_lon=max_lon,
            max_lat=max_lat,
        )
        response = self.client.get(
            "/api/nature-reserves/at_point/",
            {"lat": self.lat, "lon": self.lon},
        )
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        self.assertIsInstance(data, list)
        self.assertGreaterEqual(
            len(data),
            1,
            f"at_point should return at least one reserve; got {data}",
        )
        ids = [r["id"] for r in data]
        self.assertIn("way_999", ids)

    def test_at_point_returns_400_without_lat_or_lon(self):
        response = self.client.get("/api/nature-reserves/at_point/", {})
        self.assertEqual(response.status_code, 400)
        response = self.client.get("/api/nature-reserves/at_point/", {"lat": 52.1})
        self.assertEqual(response.status_code, 400)
        response = self.client.get("/api/nature-reserves/at_point/", {"lon": 5.2})
        self.assertEqual(response.status_code, 400)

    def test_at_point_returns_overlapping_reserves(self):
        min_lon, min_lat, max_lon, max_lat = self.bbox
        for i, reserve_id in enumerate(["way_999", "way_998"]):
            NatureReserve.objects.create(
                id=reserve_id,
                name=f"Overlap Reserve {i}",
                osm_data={
                    "type": "way",
                    "id": 999 - i,
                    "tags": {"leisure": "nature_reserve"},
                    "geometry": [
                        {"lat": 52.09, "lon": 5.19},
                        {"lat": 52.11, "lon": 5.19},
                        {"lat": 52.11, "lon": 5.21},
                        {"lat": 52.09, "lon": 5.21},
                        {"lat": 52.09, "lon": 5.19},
                    ],
                },
                tags={},
                area_type="nature_reserve",
                min_lon=min_lon,
                min_lat=min_lat,
                max_lon=max_lon,
                max_lat=max_lat,
            )
        response = self.client.get(
            "/api/nature-reserves/at_point/",
            {"lat": self.lat, "lon": self.lon},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 2, f"expected 2 overlapping reserves, got {data}")
        ids = {r["id"] for r in data}
        self.assertEqual(ids, {"way_999", "way_998"})

    def test_at_point_returns_empty_when_no_reserve_at_point(self):
        response = self.client.get(
            "/api/nature-reserves/at_point/",
            {"lat": self.lat, "lon": self.lon},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_at_point_filters_by_source(self):
        min_lon, min_lat, max_lon, max_lat = self.bbox
        NatureReserve.objects.create(
            id="osm_reserve",
            name="OSM Reserve",
            source="osm",
            osm_data=self.osm_data_with_geometry,
            tags={},
            area_type="nature_reserve",
            min_lon=min_lon,
            min_lat=min_lat,
            max_lon=max_lon,
            max_lat=max_lat,
        )
        NatureReserve.objects.create(
            id="wdpa_reserve",
            name="WDPA Reserve",
            source="wdpa",
            osm_data=self.osm_data_with_geometry,
            tags={},
            area_type="nature_reserve",
            min_lon=min_lon,
            min_lat=min_lat,
            max_lon=max_lon,
            max_lat=max_lat,
        )
        response = self.client.get(
            "/api/nature-reserves/at_point/",
            {"lat": self.lat, "lon": self.lon, "source": "osm"},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["id"], "osm_reserve")

        response = self.client.get(
            "/api/nature-reserves/at_point/",
            {"lat": self.lat, "lon": self.lon, "source": "wdpa"},
        )
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["id"], "wdpa_reserve")

    def test_at_point_filters_by_operator(self):
        min_lon, min_lat, max_lon, max_lat = self.bbox
        op1 = Operator.objects.create(name="Operator 1")
        op2 = Operator.objects.create(name="Operator 2")
        reserve1 = NatureReserve.objects.create(
            id="reserve_op1",
            name="Reserve Op1",
            osm_data=self.osm_data_with_geometry,
            tags={},
            area_type="nature_reserve",
            min_lon=min_lon,
            min_lat=min_lat,
            max_lon=max_lon,
            max_lat=max_lat,
        )
        reserve1.operators.add(op1)
        reserve2 = NatureReserve.objects.create(
            id="reserve_op2",
            name="Reserve Op2",
            osm_data=self.osm_data_with_geometry,
            tags={},
            area_type="nature_reserve",
            min_lon=min_lon,
            min_lat=min_lat,
            max_lon=max_lon,
            max_lat=max_lat,
        )
        reserve2.operators.add(op2)
        response = self.client.get(
            "/api/nature-reserves/at_point/",
            {"lat": self.lat, "lon": self.lon, "operator": op1.id},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["id"], "reserve_op1")

    def test_at_point_filters_by_protection_level(self):
        min_lon, min_lat, max_lon, max_lat = self.bbox
        NatureReserve.objects.create(
            id="strict_reserve",
            name="Strict Reserve",
            protect_class="1a",
            osm_data=self.osm_data_with_geometry,
            tags={},
            area_type="nature_reserve",
            min_lon=min_lon,
            min_lat=min_lat,
            max_lon=max_lon,
            max_lat=max_lat,
        )
        NatureReserve.objects.create(
            id="national_park_reserve",
            name="National Park",
            protect_class="2",
            osm_data=self.osm_data_with_geometry,
            tags={},
            area_type="nature_reserve",
            min_lon=min_lon,
            min_lat=min_lat,
            max_lon=max_lon,
            max_lat=max_lat,
        )
        response = self.client.get(
            "/api/nature-reserves/at_point/",
            {"lat": self.lat, "lon": self.lon, "protection_level": "strict"},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["id"], "strict_reserve")

        response = self.client.get(
            "/api/nature-reserves/at_point/",
            {"lat": self.lat, "lon": self.lon, "protection_level": "national_park"},
        )
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["id"], "national_park_reserve")
