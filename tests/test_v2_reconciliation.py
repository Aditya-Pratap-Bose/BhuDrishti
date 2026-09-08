"""
tests/test_v2_reconciliation.py
-------------------------------
Unit tests for cadastral parcel reconciliation between AI predictions and historical records.
"""

import unittest
from shapely.geometry import Polygon, mapping

from app.services.v2.reconciliation import (
    ReconciliationStatus,
    compute_iou,
    reconcile_cadastral_parcels,
)


class V2ReconciliationTests(unittest.TestCase):
    def test_compute_iou(self) -> None:
        p1 = Polygon([(0, 0), (10, 0), (10, 10), (0, 10)])  # 100
        p2 = Polygon([(5, 0), (15, 0), (15, 10), (5, 10)])  # 100, intersection = 50, union = 150
        iou = compute_iou(p1, p2)
        self.assertAlmostEqual(iou, 50.0 / 150.0, delta=0.01)

    def test_reconciliation_exact_match(self) -> None:
        p_ext = Polygon([(0, 0), (10, 0), (10, 10), (0, 10)])
        # AI polygon with 95% identical boundary
        p_ai = Polygon([(0.1, 0.1), (9.9, 0.1), (9.9, 9.9), (0.1, 9.9)])

        existing = [{"id": "EXT-101", "geometry": mapping(p_ext)}]
        ai = [{"id": "AI-201", "geometry": mapping(p_ai)}]

        report = reconcile_cadastral_parcels(existing, ai)
        self.assertEqual(report.matches_count, 1)
        self.assertEqual(report.items[0].status, ReconciliationStatus.MATCH)
        self.assertEqual(report.items[0].existing_parcel_id, "EXT-101")

    def test_reconciliation_new_parcel(self) -> None:
        p_ext = Polygon([(0, 0), (10, 0), (10, 10), (0, 10)])
        # AI parcel far away
        p_ai = Polygon([(100, 100), (110, 100), (110, 110), (100, 110)])

        existing = [{"id": "EXT-101", "geometry": mapping(p_ext)}]
        ai = [{"id": "AI-NEW", "geometry": mapping(p_ai)}]

        report = reconcile_cadastral_parcels(existing, ai)
        self.assertEqual(report.new_parcels_count, 1)
        self.assertEqual(report.missing_parcels_count, 1)

    def test_reconciliation_minor_change(self) -> None:
        p_ext = Polygon([(0, 0), (10, 0), (10, 10), (0, 10)])
        # AI parcel shifted slightly (IoU ~ 0.70)
        p_ai = Polygon([(2, 0), (10, 0), (10, 10), (2, 10)])

        existing = [{"id": "EXT-101", "geometry": mapping(p_ext)}]
        ai = [{"id": "AI-SHIFTED", "geometry": mapping(p_ai)}]

        report = reconcile_cadastral_parcels(existing, ai)
        self.assertEqual(report.minor_changes_count, 1)
        self.assertEqual(report.items[0].status, ReconciliationStatus.MINOR_CHANGE)


if __name__ == "__main__":
    unittest.main()
