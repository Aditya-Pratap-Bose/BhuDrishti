"""
tests/test_v2_quality_scorer.py
-------------------------------
Unit tests for multidimensional quality scoring and surveyor review priority.
"""

import unittest

from app.services.v2.quality.scorer import evaluate_cadastral_quality


class V2QualityScorerTests(unittest.TestCase):
    def test_high_quality_survey_unit(self) -> None:
        report = evaluate_cadastral_quality(
            raster_meta={"crs": "EPSG:32643", "gsd": 0.10, "nodata": -9999.0},
            total_features=50,
            invalid_geometry_count=0,
            overlap_count=0,
            duplicate_count=0,
            sliver_count=0,
            mean_ai_confidence=0.88,
            reconciliation_summary={"matches": 45, "minor_changes": 5, "conflicts": 0},
        )
        self.assertGreaterEqual(report.overall_quality_score, 85.0)
        self.assertEqual(report.review_priority, "LOW")
        self.assertIn("Ready for field", report.recommendation)

    def test_critical_defects_survey_unit(self) -> None:
        report = evaluate_cadastral_quality(
            raster_meta={"crs": None},  # Missing CRS
            total_features=50,
            invalid_geometry_count=15,  # 30% invalid
            overlap_count=12,
            duplicate_count=5,
            sliver_count=10,
            mean_ai_confidence=0.35,
            reconciliation_summary={"matches": 5, "minor_changes": 5, "conflicts": 10},
        )
        self.assertLess(report.overall_quality_score, 55.0)
        self.assertIn(report.review_priority, ["HIGH", "CRITICAL"])


if __name__ == "__main__":
    unittest.main()
