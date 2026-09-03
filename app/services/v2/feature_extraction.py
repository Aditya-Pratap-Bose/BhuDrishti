"""Lightweight, deterministic feature extraction for the v2 prototype.

The service intentionally produces reviewable preliminary layers rather than
claiming model-grade predictions. It keeps inference bounded and emits normal
GeoJSON that can later be replaced by trained models without changing the API.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import rasterio
from rasterio.features import shapes
from rasterio.transform import Affine


class FeatureExtractionError(ValueError):
    """Raised when a raster cannot produce a feature layer."""


def _mask_for_layer(values: np.ndarray, layer: str, percentile: float) -> np.ndarray:
    valid = np.isfinite(values)
    if not valid.any():
        raise FeatureExtractionError("Raster contains no finite pixels.")
    cutoff = float(np.percentile(values[valid], percentile))
    if layer in {"building", "land_use"}:
        return valid & (values >= cutoff)
    return valid & (values <= cutoff)


def extract_features(
    asset_path: str | Path,
    layer: str,
    threshold_percentile: float = 75.0,
) -> list[dict[str, Any]]:
    """Extract bounded preliminary polygons from a COG raster."""
    if layer not in {"building", "road", "access_corridor", "land_use"}:
        raise FeatureExtractionError("Unsupported feature layer.")
    try:
        with rasterio.open(asset_path) as dataset:
            if dataset.width * dataset.height > 16_000_000:
                raise FeatureExtractionError("Raster is too large for synchronous extraction.")
            values = dataset.read(1, masked=True).filled(np.nan).astype(np.float32)
            mask = _mask_for_layer(values, layer, threshold_percentile)
            transform = dataset.transform
            crs = dataset.crs
    except FeatureExtractionError:
        raise
    except (rasterio.errors.RasterioIOError, ValueError, OSError) as exc:
        raise FeatureExtractionError("Raster asset could not be read for feature extraction.") from exc

    output: list[dict[str, Any]] = []
    for geometry, value in shapes(mask.astype(np.uint8), mask=mask, transform=transform):
        if value != 1:
            continue
        area = abs(_polygon_area(geometry, transform))
        if area <= 0:
            continue
        output.append(
            {
                "type": "Feature",
                "geometry": geometry,
                "properties": {
                    "layer": layer,
                    "area": area,
                    "confidence": 0.35,
                    "model_name": "raster-threshold-baseline",
                    "model_version": "v2.0",
                    "crs": crs.to_string() if crs else None,
                },
            }
        )
        if len(output) >= 5000:
            break
    return output


def _polygon_area(geometry: dict[str, Any], transform: Affine) -> float:
    """Estimate pixel-space area; exact geodesic area belongs in GIS post-processing."""
    coordinates = geometry.get("coordinates", [])
    rings = coordinates[0] if coordinates else []
    area = 0.0
    for (x1, y1), (x2, y2) in zip(rings, rings[1:]):
        area += x1 * y2 - x2 * y1
    scale = abs(transform.a * transform.e - transform.b * transform.d)
    return abs(area) * scale / 2
