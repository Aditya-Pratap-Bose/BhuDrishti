"""
app/services/v2/vectorization/normalization.py
----------------------------------------------
Geometry normalization for cadastral land parcels.
Enforces standard ring orientation (exterior counter-clockwise, interior clockwise)
and coordinate precision normalization.
"""

from __future__ import annotations

from shapely.geometry import Polygon
from shapely.ops import orient


def normalize_polygon(geom: Polygon, precision_decimals: int = 6) -> Polygon:
    """
    Ensure standard CCW exterior ring orientation, CW interior rings,
    and round coordinates to prevent floating point noise.
    """
    if geom.is_empty:
        return geom

    # Orient exterior counter-clockwise (sign=1.0)
    oriented = orient(geom, sign=1.0)

    # Round coordinates to eliminate micro-fluctuations
    exterior_coords = [
        (round(x, precision_decimals), round(y, precision_decimals))
        for x, y in oriented.exterior.coords
    ]
    interior_coords = [
        [
            (round(x, precision_decimals), round(y, precision_decimals))
            for x, y in ring.coords
        ]
        for ring in oriented.interiors
    ]

    return Polygon(exterior_coords, interior_coords)
