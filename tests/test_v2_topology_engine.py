"""
tests/test_v2_topology_engine.py
--------------------------------
Unit tests for CadastralTopologyEngine and cross-layer validation.
"""

import unittest
import uuid
from shapely.geometry import Polygon, mapping

from app.models.v2.validation import IssueSeverity, IssueType
from app.services.v2.topology.engine import CadastralTopologyEngine


class V2TopologyEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = CadastralTopologyEngine()
        self.project_id = uuid.uuid4()

    def test_parcel_overlap_detection(self) -> None:
        p1 = Polygon([(0, 0), (10, 0), (10, 10), (0, 10)])
        # Overlaps p1 on the right half (x from 5 to 10)
        p2 = Polygon([(5, 0), (15, 0), (15, 10), (5, 10)])

        features = [
            {"id": "P-1", "geometry": mapping(p1)},
            {"id": "P-2", "geometry": mapping(p2)},
        ]

        issues = self.engine.validate_parcels(features, project_id=self.project_id)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].issue_type, IssueType.PARCEL_OVERLAP)
        self.assertEqual(issues[0].severity, IssueSeverity.ERROR)
        self.assertIn("overlaps", issues[0].description)

    def test_duplicate_detection(self) -> None:
        p1 = Polygon([(0, 0), (10, 0), (10, 10), (0, 10)])
        # 99.9% identical duplicate
        p2 = Polygon([(0.01, 0), (10.01, 0), (10.01, 10), (0.01, 10)])

        features = [
            {"id": "P-A", "geometry": mapping(p1)},
            {"id": "P-B", "geometry": mapping(p2)},
        ]

        issues = self.engine.validate_parcels(features, project_id=self.project_id)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].issue_type, IssueType.DUPLICATE)
        self.assertEqual(issues[0].severity, IssueSeverity.CRITICAL)

    def test_sliver_detection(self) -> None:
        sliver = Polygon([(0, 0), (0.1, 0), (0.1, 0.1), (0, 0.1)])  # area = 0.01 sqm

        features = [{"id": "SLV-1", "geometry": mapping(sliver)}]
        issues = self.engine.validate_parcels(features, project_id=self.project_id, min_area_sqm=5.0)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].issue_type, IssueType.SLIVER)
        self.assertEqual(issues[0].severity, IssueSeverity.WARNING)

    def test_cross_layer_building_crossing_boundary(self) -> None:
        parcel_a = Polygon([(0, 0), (10, 0), (10, 10), (0, 10)])
        parcel_b = Polygon([(10, 0), (20, 0), (20, 10), (10, 10)])
        # Building sitting across boundary (x from 8 to 12)
        building = Polygon([(8, 2), (12, 2), (12, 6), (8, 6)])

        parcels = [
            {"id": "P-A", "geometry": mapping(parcel_a)},
            {"id": "P-B", "geometry": mapping(parcel_b)},
        ]
        buildings = [
            {"id": "BLD-1", "geometry": mapping(building)},
        ]

        issues = self.engine.validate_cross_layer(parcels, buildings, project_id=self.project_id)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].issue_type, IssueType.BUILDING_CROSSING_BOUNDARY)
        self.assertEqual(issues[0].severity, IssueSeverity.CRITICAL)

    def test_cross_layer_building_outside_parcels(self) -> None:
        parcel = Polygon([(0, 0), (10, 0), (10, 10), (0, 10)])
        # Building far away outside parcel
        building = Polygon([(50, 50), (60, 50), (60, 60), (50, 60)])

        parcels = [{"id": "P-A", "geometry": mapping(parcel)}]
        buildings = [{"id": "BLD-ORPHAN", "geometry": mapping(building)}]

        issues = self.engine.validate_cross_layer(parcels, buildings, project_id=self.project_id)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].issue_type, IssueType.BUILDING_OUTSIDE_PARCEL)
        self.assertEqual(issues[0].severity, IssueSeverity.WARNING)


if __name__ == "__main__":
    unittest.main()
