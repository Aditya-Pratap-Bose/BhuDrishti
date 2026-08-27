"""
app/services/gis/raster_service.py
----------------------------------
Local raster utilities for GIS processing.

This project is designed as a hybrid stack: the AI mask generation may come
from Colab, but the geometry and metadata processing can still be done locally.
This file provides small helper functions to open raster files, read metadata,
and compute a rough geospatial footprint for a raster tile without requiring the
full app to be tied to a specific backend.

It intentionally keeps the API lightweight so it can be reused in local scripts,
STAC-driven workflows, or future offline processing.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("bhudrishti.raster_service")

try:
    import rasterio
    from rasterio.coords import BoundingBox
    from rasterio.windows import Window
except ImportError:  # pragma: no cover
    rasterio = None  # type: ignore[assignment]
    BoundingBox = Any  # type: ignore[misc,assignment]
    Window = Any  # type: ignore[misc,assignment]


class RasterServiceError(RuntimeError):
    """Raised when local raster processing is requested but a required dependency is missing."""


def require_rasterio() -> None:
    if rasterio is None:
        raise RasterServiceError(
            "RasterIO is not installed. Install rasterio to use local raster processing."
        )


def read_raster_metadata(raster_path: str) -> dict[str, Any]:
    """Read basic raster metadata for a local file."""
    require_rasterio()
    with rasterio.open(raster_path) as src:
        return {
            "driver": src.driver,
            "width": src.width,
            "height": src.height,
            "count": src.count,
            "crs": str(src.crs) if src.crs else None,
            "bounds": src.bounds,
            "transform": src.transform,
            "nodata": src.nodata,
            "dtype": src.dtypes[0] if src.dtypes else None,
        }


def get_raster_bounds(raster_path: str) -> BoundingBox:
    """Return the geospatial bounds of a raster tile."""
    require_rasterio()
    with rasterio.open(raster_path) as src:
        return src.bounds


def read_window(raster_path: str, window: tuple[int, int, int, int]) -> Any:
    """Read a raster window from a local file using a (row_off, col_off, height, width) tuple."""
    require_rasterio()
    row_off, col_off, height, width = window
    with rasterio.open(raster_path) as src:
        return src.read(window=Window(col_off, row_off, width, height))


def estimate_bbox_from_raster(raster_path: str) -> tuple[float, float, float, float]:
    """Return (min_lon, min_lat, max_lon, max_lat) from raster bounds."""
    bounds = get_raster_bounds(raster_path)
    return (
        float(bounds.left),
        float(bounds.bottom),
        float(bounds.right),
        float(bounds.top),
    )
