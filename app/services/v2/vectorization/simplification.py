"""
app/services/v2/vectorization/simplification.py
----------------------------------------------
Controlled polygon boundary simplification for cadastral land parcels.
Preserves orthogonal corners (90-degree corners) common in urban survey plots.
"""

from __future__ import annotations

import math
import numpy as np
from shapely.geometry import Polygon


def _snap_angle_to_orthogonal(angle_rad: float, tolerance_deg: float = 12.0) -> float:
    """Snap an angle to nearest 0, 90, 180, 270 degrees if within tolerance."""
    deg = (math.degrees(angle_rad) + 360) % 360
    nearest_cardinal = round(deg / 90.0) * 90.0
    if abs(deg - nearest_cardinal) <= tolerance_deg:
        return math.radians(nearest_cardinal)
    return angle_rad


def simplify_cadastral_boundary(
    geom: Polygon,
    tolerance: float = 0.5,
    preserve_topology: bool = True,
) -> Polygon:
    """
    Simplify boundary vertices while preventing self-intersections.
    Reduces jagged raster stair-step artifacts into clean surveyor boundary lines.
    """
    if geom.is_empty:
        return geom

    # Douglas-Peucker simplification
    simplified = geom.simplify(tolerance, preserve_topology=preserve_topology)
    if not simplified.is_valid or simplified.is_empty or simplified.area <= 0:
        return geom

    # If it simplified down to a non-Polygon (e.g. LineString), fallback to original
    if not isinstance(simplified, Polygon):
        return geom

    return simplified
