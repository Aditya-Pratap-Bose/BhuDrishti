"""
app/services/v2/vectorization/__init__.py
----------------------------------------
End-to-end vectorization pipeline for cadastral feature extraction.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from rasterio.transform import Affine
from shapely.geometry import mapping

from app.services.v2.vectorization.geometry_cleanup import (
    fill_small_holes,
    remove_small_components,
    repair_polygon,
)
from app.services.v2.vectorization.metrics import calculate_crs_aware_metrics
from app.services.v2.vectorization.normalization import normalize_polygon
from app.services.v2.vectorization.polygonize import mask_to_polygons
from app.services.v2.vectorization.simplification import simplify_cadastral_boundary

__all__ = [
    "mask_to_polygons",
    "repair_polygon",
    "remove_small_components",
    "fill_small_holes",
    "simplify_cadastral_boundary",
    "calculate_crs_aware_metrics",
    "normalize_polygon",
    "vectorize_candidate_mask",
]


def vectorize_candidate_mask(
    mask: np.ndarray,
    transform: Affine,
    crs: str | None = None,
    min_area_sqm: float = 10.0,
    simplify_tolerance: float = 0.5,
) -> list[dict[str, Any]]:
    """
    Complete cadastral vectorization pipeline:
    Mask -> Polygonize -> Component filtering -> Repair -> Simplification -> Normalization -> Metric calculation.
    """
    raw_polys = mask_to_polygons(mask, transform)
    processed_features: list[dict[str, Any]] = []

    for poly in raw_polys:
        # 1. Component removal
        cleaned = remove_small_components(poly, min_area=min_area_sqm * 0.1)
        if cleaned is None or cleaned.is_empty:
            continue

        # 2. Repair geometry
        repaired = repair_polygon(cleaned)
        if repaired.is_empty or not hasattr(repaired, "exterior"):
            continue

        # 3. Fill small holes
        filled = fill_small_holes(repaired, max_hole_area=min_area_sqm * 0.2)

        # 4. Simplify boundary
        simplified = simplify_cadastral_boundary(filled, tolerance=simplify_tolerance)

        # 5. Normalize
        normalized = normalize_polygon(simplified)

        # 6. Calculate CRS-aware metrics
        metrics = calculate_crs_aware_metrics(normalized, source_crs=crs)
        if metrics["area_sqm"] < min_area_sqm:
            continue

        processed_features.append(
            {
                "geometry": mapping(normalized),
                "properties": metrics,
            }
        )

    return processed_features
