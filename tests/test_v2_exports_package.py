"""
tests/test_v2_exports_package.py
--------------------------------
Unit tests for multi-format exports and standalone cadastral package validation gating.
"""

import tempfile
import unittest
from shapely.geometry import Polygon, mapping

from app.services.v2.exports import (
    export_to_csv,
    export_to_geojson,
    generate_cadastral_export_package,
    run_export_validation_gate,
)


class V2ExportsPackageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.poly = Polygon([(500000, 2300000), (500020, 2300000), (500020, 2300020), (500000, 2300020)])
        self.feature = {
            "type": "Feature",
            "geometry": mapping(self.poly),
            "properties": {
                "ulpin": "22100010000123",
                "area_sqm": 400.0,
                "perimeter_m": 80.0,
                "land_use": "RESIDENTIAL",
                "owner_name": "Ramesh Kumar",
                "survey_unit": "SU-RAIPUR-001",
            },
        }

    def test_geojson_export(self) -> None:
        geojson = export_to_geojson([self.feature], crs="EPSG:32643")
        self.assertEqual(geojson["type"], "FeatureCollection")
        self.assertEqual(len(geojson["features"]), 1)
        self.assertIn("metadata", geojson)

    def test_csv_export(self) -> None:
        csv_text = export_to_csv([self.feature])
        self.assertIn("ulpin", csv_text)
        self.assertIn("22100010000123", csv_text)
        self.assertIn("Ramesh Kumar", csv_text)

    def test_validation_gate_blocked_by_topology_errors(self) -> None:
        gate = run_export_validation_gate(
            [self.feature],
            crs="EPSG:32643",
            unresolved_topology_errors=3,  # 3 blocking errors
        )
        self.assertFalse(gate["is_ready"])
        self.assertEqual(gate["status"], "BLOCKED")
        self.assertTrue(any("unresolved" in r for r in gate["reasons"]))

    def test_validation_gate_blocked_by_missing_crs(self) -> None:
        gate = run_export_validation_gate(
            [self.feature],
            crs=None,
            unresolved_topology_errors=0,
        )
        self.assertFalse(gate["is_ready"])
        self.assertTrue(any("CRS missing" in r for r in gate["reasons"]))

    def test_cadastral_package_ready(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            result = generate_cadastral_export_package(
                project_meta={"name": "Raipur Urban Survey", "state": "22", "district": "10", "ulb": "RMC"},
                survey_unit="SU-RAIPUR-001",
                features=[self.feature],
                crs="EPSG:32643",
                unresolved_topology_errors=0,
                output_dir=temp_dir,
            )
            self.assertEqual(result["status"], "READY")
            self.assertTrue(result["package_id"].startswith("BHU-PKG-"))
            self.assertIsNotNone(result["manifest"].get("sha256_checksum"))
            self.assertEqual(result["manifest"]["package_version"], "BhuDrishti-Cadastral-Package/v2.0")
            self.assertEqual(result["feature_count"], 1)


if __name__ == "__main__":
    unittest.main()
