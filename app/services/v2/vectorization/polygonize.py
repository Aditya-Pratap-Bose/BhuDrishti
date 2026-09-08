"""
app/services/v2/vectorization/polygonize.py
------------------------------------------
Converts binary segmentation masks into Shapely geometries using affine spatial transforms.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from rasterio.features import shapes
from rasterio.transform import Affine
from shapely.geometry import Polygon, shape


def mask_to_polygons(
    mask: np.ndarray,
    transform: Affine,
    min_pixels: int = 4,
) -> list[Polygon]:
    """
    Convert a 2D boolean or uint8 mask into a list of Shapely Polygons.
    Only extracts foreground features (value == 1).
    """
    binary_mask = (mask.astype(np.uint8) == 1)
    if not np.any(binary_mask):
        return []

    polygons: list[Polygon] = []
    for geom_dict, val in shapes(binary_mask.astype(np.uint8), mask=binary_mask, transform=transform):
        if val != 1:
            continue
        geom = shape(geom_dict)
        if geom.is_empty:
            continue
        if isinstance(geom, Polygon):
            polygons.append(geom)
        else:
            # Handle MultiPolygon
            for part in getattr(geom, "geoms", []):
                if isinstance(part, Polygon) and not part.is_empty:
                    polygons.append(part)

    return polygons
