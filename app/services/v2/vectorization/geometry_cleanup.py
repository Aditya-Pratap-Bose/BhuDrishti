"""
app/services/v2/vectorization/geometry_cleanup.py
-------------------------------------------------
Cadastral geometry repair, sliver/island removal, and hole filling.
"""

from __future__ import annotations

from shapely.geometry import MultiPolygon, Polygon
from shapely.validation import make_valid


def repair_polygon(geom: Polygon | MultiPolygon) -> Polygon | MultiPolygon:
    """Repair self-intersections, inverted rings, and duplicate vertices."""
    if geom.is_valid:
        return geom
    cleaned = make_valid(geom)
    if cleaned.is_empty:
        raise ValueError("Geometry cleanup resulted in empty geometry.")
    return cleaned


def remove_small_components(
    geom: Polygon | MultiPolygon,
    min_area: float = 5.0,
) -> Polygon | MultiPolygon | None:
    """Remove tiny disjoint slivers or islands from a parcel geometry."""
    if geom.is_empty:
        return None

    if isinstance(geom, Polygon):
        return geom if geom.area >= min_area else None

    # MultiPolygon case
    valid_parts = [p for p in geom.geoms if p.area >= min_area]
    if not valid_parts:
        return None
    if len(valid_parts) == 1:
        return valid_parts[0]
    return MultiPolygon(valid_parts)


def fill_small_holes(geom: Polygon, max_hole_area: float = 10.0) -> Polygon:
    """Fill internal donut holes in parcel boundaries if smaller than max_hole_area."""
    if not geom.interiors:
        return geom

    kept_interiors = [
        interior for interior in geom.interiors
        if Polygon(interior).area > max_hole_area
    ]
    return Polygon(geom.exterior.coords, [ring.coords for ring in kept_interiors])
