"""Focused quality checks for v2 cadastral topology reporting."""

import unittest

from shapely.geometry import Polygon

from app.services.v2.topology import enforce_cadastral_topology, inspect_topology


class V2TopologyTests(unittest.TestCase):
    def test_reports_overlap_area_and_metrics(self) -> None:
        target = Polygon([(0, 0), (2, 0), (2, 2), (0, 2)])
        neighbour = Polygon([(1, 0), (3, 0), (3, 2), (1, 2)])

        report = inspect_topology(target, [neighbour])

        self.assertTrue(report.valid)
        self.assertEqual(report.overlaps, 1)
        self.assertAlmostEqual(report.overlap_area, 2.0)
        self.assertAlmostEqual(report.area, 4.0)
        self.assertAlmostEqual(report.perimeter, 8.0)
        self.assertFalse(report.near_duplicate)

    def test_flags_near_duplicate_polygons(self) -> None:
        target = Polygon([(0, 0), (2, 0), (2, 2), (0, 2)])
        neighbour = Polygon([(0.001, 0), (2.001, 0), (2.001, 2), (0.001, 2)])

        report = inspect_topology(target, [neighbour])

        self.assertTrue(report.near_duplicate)

    def test_cleanup_removes_neighbour_overlap(self) -> None:
        target = Polygon([(0, 0), (2, 0), (2, 2), (0, 2)])
        neighbour = Polygon([(1, 0), (3, 0), (3, 2), (1, 2)])

        cleaned = enforce_cadastral_topology(target, [neighbour])

        self.assertTrue(cleaned.is_valid)
        self.assertAlmostEqual(cleaned.area, 2.0)
        self.assertAlmostEqual(cleaned.intersection(neighbour).area, 0.0)


if __name__ == "__main__":
    unittest.main()
