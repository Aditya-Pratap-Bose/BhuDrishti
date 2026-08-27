"""
app/services/gis/stac_service.py
--------------------------------
STAC helper service for Earth-observation catalogs.

This module provides a small, reusable layer for working with STAC APIs or static
STAC JSON documents. It is not the full satellite processing engine itself; it is
just the catalog/metadata discovery layer that helps find geospatial scenes for a
bounding box.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("bhudrishti.stac_service")

try:
    import httpx
except ImportError:  # pragma: no cover
    httpx = None  # type: ignore[assignment]


class STACError(RuntimeError):
    """Raised when STAC metadata cannot be fetched or parsed."""


def fetch_stac_json(url: str, timeout: float = 30.0) -> dict[str, Any]:
    """Fetch a STAC JSON document from a URL."""
    if httpx is None:
        raise STACError("httpx is required for STAC requests.")

    response = httpx.get(url, timeout=timeout)
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict):
        raise STACError(f"STAC response from {url} was not a JSON object.")
    return data


def extract_item_bboxes(stac_response: dict[str, Any]) -> list[tuple[float, float, float, float]]:
    """Extract bbox values from a STAC collection or item list."""
    items = stac_response.get("features", [])
    if not isinstance(items, list):
        return []

    bboxes: list[tuple[float, float, float, float]] = []
    for item in items:
        bbox = item.get("bbox")
        if isinstance(bbox, list) and len(bbox) == 4:
            try:
                bboxes.append((float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])))
            except (TypeError, ValueError):
                continue
    return bboxes


def find_items_for_bbox(stac_url: str, bbox: tuple[float, float, float, float]) -> list[dict[str, Any]]:
    """Query a STAC catalog and return matching items for the given bbox."""
    data = fetch_stac_json(stac_url)
    items = data.get("features", [])
    if not isinstance(items, list):
        return []

    min_lon, min_lat, max_lon, max_lat = bbox
    matches: list[dict[str, Any]] = []
    for item in items:
        item_bbox = item.get("bbox")
        if not isinstance(item_bbox, list) or len(item_bbox) != 4:
            continue

        try:
            item_min_lon, item_min_lat, item_max_lon, item_max_lat = [float(v) for v in item_bbox]
        except (TypeError, ValueError):
            continue

        intersects = not (
            item_max_lon < min_lon
            or item_max_lat < min_lat
            or item_min_lon > max_lon
            or item_min_lat > max_lat
        )
        if intersects:
            matches.append(item)
    return matches


def build_stac_collection_url(base_url: str, collection_id: str) -> str:
    """Build a collection endpoint with the typical STAC URL pattern."""
    if base_url.endswith("/"):
        return f"{base_url}collections/{collection_id}"
    return f"{base_url}/collections/{collection_id}"
