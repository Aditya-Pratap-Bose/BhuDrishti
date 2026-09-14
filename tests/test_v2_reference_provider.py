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


class TestReferenceBenchmark(unittest.TestCase):
    """Test the reference benchmark computation."""

    def test_benchmark_empty_reference_returns_not_evaluated(self):
        from unittest.mock import MagicMock
        from app.api.v2.reference_data import compute_reference_benchmark, BenchmarkRequest
        import uuid

        db = MagicMock()
        proj = MagicMock()
        proj.id = uuid.uuid4()
        db.query().filter().first.return_value = proj

        req = BenchmarkRequest(
            project_id=proj.id,
            ai_features=[{"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[[0,0],[1,0],[1,1],[0,0]]]}, "properties": {}}],
            reference_features=[],
        )
        user = MagicMock()
        user.id = uuid.uuid4()
        res = compute_reference_benchmark(req, current_user=user, db=db)
        self.assertEqual(res.benchmark_status, "NOT_EVALUATED")
        self.assertEqual(res.reference_count, 0)
        self.assertEqual(res.ai_count, 1)

    def test_benchmark_with_matching_data_returns_evaluated(self):
        from unittest.mock import MagicMock
        from app.api.v2.reference_data import compute_reference_benchmark, BenchmarkRequest
        import uuid

        poly = {"type": "Polygon", "coordinates": [[[78.40, 17.30], [78.41, 17.30], [78.41, 17.31], [78.40, 17.31], [78.40, 17.30]]]}
        ai_feature = {"type": "Feature", "geometry": poly, "properties": {"id": "AI-001", "confidence": 0.92}}
        ref_feature = {"type": "Feature", "geometry": poly, "properties": {"reference_id": "REF-001"}}

        db = MagicMock()
        proj = MagicMock()
        proj.id = uuid.uuid4()
        db.query().filter().first.return_value = proj

        req = BenchmarkRequest(
            project_id=proj.id,
            ai_features=[ai_feature],
            reference_features=[ref_feature],
        )
        user = MagicMock()
        user.id = uuid.uuid4()
        res = compute_reference_benchmark(req, current_user=user, db=db)
        self.assertEqual(res.benchmark_status, "EVALUATED")
        self.assertEqual(res.reference_count, 1)
        self.assertEqual(res.ai_count, 1)
        self.assertIn("summary", res.reconciliation_summary)
        self.assertEqual(res.reconciliation_summary["summary"]["matches"], 1)
        self.assertIn("overall_quality_score", res.quality_evaluation)


if __name__ == "__main__":
    unittest.main()
