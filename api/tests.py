from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.core.management import call_command
from django.core.management.base import CommandError
from io import StringIO
from api.models import NatureReserve


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
                },
                "tags": {"boundary": "protected_area", "name": "Protected Area Test"},
                "area_type": "protected_area_class_4",
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
        NatureReserve.objects.create(
            id="way_123456",
            name="Old Name",
            osm_data={},
            tags={},
            area_type="nature_reserve",
        )

        mock_reserves = [
            {
                "id": "way_123456",
                "name": "Updated Name",
                "osm_data": {"type": "way", "id": 123456, "tags": {}},
                "tags": {},
                "area_type": "nature_reserve",
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
        NatureReserve.objects.create(
            id="way_111",
            name="Old Reserve",
            osm_data={},
            tags={},
            area_type="nature_reserve",
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
