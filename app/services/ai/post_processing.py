"""
app/services/ai/post_processing.py
----------------------------------
Post-processing utilities for AI-generated parcel masks.

The actual segmentation model may return raw masks or rough polygons, and this
layer cleans them into a smaller, valid GeoJSON parcel output that can be saved
into the app and displayed in the frontend.
"""

from __future__ import annotations

import logging
from typing import Any

from shapely.geometry import shape
from shapely.ops import unary_union
from shapely.validation import make_valid

logger = logging.getLogger("bhudrishti.post_processing")


def normalize_geometry(feature: dict[str, Any]) -> dict[str, Any]:
    """Normalize a raw feature so it is valid GeoJSON-like geometry."""
    geometry = feature.get("geometry") or {}
    geom_type = geometry.get("type")
    if geom_type not in {"Polygon", "MultiPolygon"}:
        raise ValueError(f"Unsupported geometry type: {geom_type}")

    polygon = shape(geometry)
    fixed = make_valid(polygon)
    if fixed.geom_type == "GeometryCollection":
        fixed = unary_union([part for part in fixed.geoms if part.geom_type in {"Polygon", "MultiPolygon"}])

    if fixed.is_empty:
        raise ValueError("AI result produced an empty geometry after cleanup.")

    if fixed.geom_type == "MultiPolygon":
        coords = [list(geom.exterior.coords) for geom in fixed.geoms]
        return {
            "type": "MultiPolygon",
            "coordinates": [list(map(list, c)) for c in coords],
        }

    return {
        "type": "Polygon",
        "coordinates": [list(map(list, fixed.exterior.coords))],
    }


def clean_feature_collection(raw_geojson: dict[str, Any]) -> dict[str, Any]:
    """Clean a raw AI output GeoJSON into a smaller, safer parcel collection."""
    features = raw_geojson.get("features") or []
    cleaned_features: list[dict[str, Any]] = []

    for feature in features:
        props = feature.get("properties") or {}
        geometry = normalize_geometry(feature)
        cleaned_features.append({
            "type": "Feature",
            "properties": {
                "ulpin": props.get("ulpin", "AUTO-ULPIN"),
                "area_sqm": props.get("area_sqm", 0.0),
                "perimeter_m": props.get("perimeter_m", 0.0),
                "land_use": props.get("land_use", "Unclassified"),
            },
            "geometry": geometry,
        })

    return {"type": "FeatureCollection", "features": cleaned_features}
