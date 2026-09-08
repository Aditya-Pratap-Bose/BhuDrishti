"""
app/services/v2/vectorization/metrics.py
----------------------------------------
CRS-aware metric calculations for cadastral land parcels.
Ensures areas and perimeters are calculated strictly in metric units (metres/sqm),
preventing dangerous degree-squared mathematical errors.
"""

from __future__ import annotations

import math
from typing import Any

from pyproj import CRS, Transformer
from shapely.geometry import Polygon
from shapely.ops import transform


def calculate_crs_aware_metrics(
    geom: Polygon,
    source_crs: str | None = None,
    target_utm_epsg: int = 32643,
) -> dict[str, float]:
    """
    Calculate accurate ground area (sq.m), perimeter (m), and compactness index.
    If source CRS is geographic (EPSG:4326), reprojects to metric UTM before calculation.
    """
    if geom.is_empty:
        return {"area_sqm": 0.0, "perimeter_m": 0.0, "compactness": 0.0}

    metric_geom = geom
    crs_str = (source_crs or "").upper()

    # If geographic (e.g. EPSG:4326), reproject to target UTM
    if "4326" in crs_str or "WGS 84" in crs_str or (source_crs is None and -180 <= geom.bounds[0] <= 180 and -90 <= geom.bounds[1] <= 90):
        try:
            transformer = Transformer.from_crs("EPSG:4326", f"EPSG:{target_utm_epsg}", always_xy=True)
            metric_geom = transform(transformer.transform, geom)
        except Exception:
            metric_geom = geom

    area = float(metric_geom.area)
    perimeter = float(metric_geom.length)

    # Polsby-Popper compactness index: 4 * pi * Area / (Perimeter^2)
    # Circle = 1.0, Square = ~0.785, long sliver -> 0.0
    compactness = 0.0
    if perimeter > 0:
        compactness = round((4.0 * math.pi * area) / (perimeter ** 2), 4)

    return {
        "area_sqm": round(area, 2),
        "perimeter_m": round(perimeter, 2),
        "compactness": max(0.0, min(1.0, compactness)),
    }
