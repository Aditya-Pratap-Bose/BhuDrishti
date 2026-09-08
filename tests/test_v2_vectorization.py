"""
tests/test_v2_vectorization.py
------------------------------
Unit tests for V2 cadastral vectorization, boundary cleanup, and CRS-aware metrics.
"""

import unittest
import numpy as np
from rasterio.transform import from_origin
from shapely.geometry import MultiPolygon, Polygon

from app.services.v2.vectorization import (
    calculate_crs_aware_metrics,
    fill_small_holes,
    mask_to_polygons,
    normalize_polygon,
    remove_small_components,
    repair_polygon,
    simplify_cadastral_boundary,
    vectorize_candidate_mask,
)


class V2VectorizationTests(unittest.TestCase):
    def test_mask_to_polygons(self) -> None:
        mask = np.zeros((10, 10), dtype=np.uint8)
        mask[2:6, 2:6] = 1
        transform = from_origin(0, 10, 1, 1)

        polys = mask_to_polygons(mask, transform)
        self.assertEqual(len(polys), 1)
        self.assertAlmostEqual(polys[0].area, 16.0)

    def test_repair_invalid_polygon(self) -> None:
        # Self-intersecting bowtie polygon
        bowtie = Polygon([(0, 0), (2, 2), (2, 0), (0, 2), (0, 0)])
        self.assertFalse(bowtie.is_valid)

        repaired = repair_polygon(bowtie)
        self.assertTrue(repaired.is_valid)

    def test_remove_small_components(self) -> None:
        p_large = Polygon([(0, 0), (10, 0), (10, 10), (0, 10)])
        p_tiny = Polygon([(20, 20), (20.1, 20), (20.1, 20.1), (20, 20.1)])
        multi = MultiPolygon([p_large, p_tiny])

        cleaned = remove_small_components(multi, min_area=5.0)
        self.assertIsInstance(cleaned, Polygon)
        self.assertAlmostEqual(cleaned.area, 100.0)

    def test_fill_small_holes(self) -> None:
        exterior = [(0, 0), (10, 0), (10, 10), (0, 10)]
        small_hole = [(2, 2), (3, 2), (3, 3), (2, 3)]  # area = 1.0
        poly_with_hole = Polygon(exterior, [small_hole])
        self.assertEqual(len(poly_with_hole.interiors), 1)

        filled = fill_small_holes(poly_with_hole, max_hole_area=2.0)
        self.assertEqual(len(filled.interiors), 0)

    def test_simplify_cadastral_boundary(self) -> None:
        # Stair-step jagged coordinates
        coords = [(0, 0), (1, 0), (1, 0.1), (2, 0.1), (2, 2), (0, 2), (0, 0)]
        poly = Polygon(coords)
        simplified = simplify_cadastral_boundary(poly, tolerance=0.5)
        self.assertTrue(simplified.is_valid)
        self.assertLess(len(simplified.exterior.coords), len(coords))

    def test_crs_aware_metrics(self) -> None:
        # UTM 32643 polygon 10m x 20m
        utm_poly = Polygon([(500000, 2300000), (500010, 2300000), (500010, 2300020), (500000, 2300020)])
        metrics = calculate_crs_aware_metrics(utm_poly, source_crs="EPSG:32643")
        self.assertAlmostEqual(metrics["area_sqm"], 200.0, delta=0.5)
        self.assertAlmostEqual(metrics["perimeter_m"], 60.0, delta=0.5)
        self.assertGreater(metrics["compactness"], 0.6)

    def test_normalize_polygon(self) -> None:
        # Clockwise polygon (negative orientation)
        cw_poly = Polygon([(0, 0), (0, 5), (5, 5), (5, 0), (0, 0)])
        normalized = normalize_polygon(cw_poly)
        self.assertTrue(normalized.exterior.is_ccw)

    def test_vectorize_candidate_mask_pipeline(self) -> None:
        mask = np.zeros((20, 20), dtype=np.uint8)
        mask[4:16, 4:16] = 1  # 12x12 = 144 sqm
        transform = from_origin(500000, 2300020, 1.0, 1.0)

        results = vectorize_candidate_mask(
            mask, transform, crs="EPSG:32643", min_area_sqm=50.0, simplify_tolerance=0.2
        )
        self.assertEqual(len(results), 1)
        self.assertAlmostEqual(results[0]["properties"]["area_sqm"], 144.0, delta=1.0)


if __name__ == "__main__":
    unittest.main()
