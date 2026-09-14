"""Tests for bounded Telangana ArcGIS reference retrieval."""

import unittest
from unittest.mock import Mock

from app.core.exceptions import ReconciliationError
from app.services.v2.reference_data import TelanganaArcGISReferenceProvider


class TelanganaReferenceProviderTests(unittest.TestCase):
    def test_bounded_query_is_normalized(self) -> None:
        session = Mock()
        response = Mock()
        response.json.return_value = {
            "type": "FeatureCollection",
            "features": [{
                "id": 42,
                "geometry": {"type": "Polygon", "coordinates": [[[78.4, 17.3], [78.5, 17.3], [78.5, 17.4], [78.4, 17.3]]]},
                "properties": {"PLOT_NO": "P-42"},
            }],
        }
        session.get.return_value = response

        result = TelanganaArcGISReferenceProvider(session=session).search([78.4, 17.3, 78.5, 17.4])

        response.raise_for_status.assert_called_once_with()
        params = session.get.call_args.kwargs["params"]
        self.assertEqual(params["geometry"], "78.4,17.3,78.5,17.4")
        self.assertEqual(params["f"], "geojson")
        self.assertEqual(result["features"][0]["properties"]["parcel_number"], "P-42")
        self.assertEqual(result["features"][0]["properties"]["state"], "Telangana")

    def test_oversized_bbox_is_rejected_before_network(self) -> None:
        session = Mock()
        with self.assertRaises(ReconciliationError):
            TelanganaArcGISReferenceProvider(session=session).search([78.0, 17.0, 78.2, 17.1])
        session.get.assert_not_called()


if __name__ == "__main__":
    unittest.main()
