"""
app/services/v2/exports/geojson_exporter.py
-------------------------------------------
Standardized GeoJSON export utility with cadastral metadata headers and CRS tags.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def export_to_geojson(
    features: list[dict[str, Any]],
    output_path: str | Path | None = None,
    crs: str = "EPSG:4326",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Package spatial features into a valid GeoJSON FeatureCollection."""
    collection: dict[str, Any] = {
        "type": "FeatureCollection",
        "crs": {
            "type": "name",
            "properties": {"name": f"urn:ogc:def:crs:OGC:1.3:{crs}" if ":" in crs else crs},
        },
        "metadata": {
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "feature_count": len(features),
            **(metadata or {}),
        },
        "features": features,
    }

    if output_path:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            json.dump(collection, f, indent=2)

    return collection
