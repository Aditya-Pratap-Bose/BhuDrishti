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


EARTH_EQUATORIAL_RADIUS = 6378137.0


def from4326_to3857(lat: float, lon: float) -> tuple[float, float]:
    """Convert EPSG:4326 latitude/longitude to EPSG:3857 spherical Mercator coordinates."""
    import math
    xtile = math.radians(lon) * EARTH_EQUATORIAL_RADIUS
    ytile = math.log(math.tan(math.radians(45 + lat / 2.0))) * EARTH_EQUATORIAL_RADIUS
    return (xtile, ytile)


def deg2num(lat: float, lon: float, zoom: int) -> tuple[float, float]:
    """Convert EPSG:4326 coordinate to continuous tile index at the given zoom level."""
    import math
    lat_r = math.radians(lat)
    n = 2 ** zoom
    xtile = (lon + 180.0) / 360.0 * n
    ytile = (1.0 - math.log(math.tan(lat_r) + 1.0 / math.cos(lat_r)) / math.pi) / 2.0 * n
    return (xtile, ytile)


def stitch_tms_to_geotiff(
    bbox: tuple[float, float, float, float] | list[float],
    zoom: int,
    source_url: str,
    output_path: str,
    overwrite: bool = True,
) -> str:
    """
    Downloads high-resolution XYZ tiles for the bounding box and stitches them
    directly into a georeferenced GeoTIFF using rasterio and Pillow.
    This eliminates any native C++ GDAL binding dependency.
    """
    import concurrent.futures
    import io
    import itertools
    import math
    from pathlib import Path
    import numpy as np
    from PIL import Image
    import httpx
    from rasterio.transform import from_bounds

    require_rasterio()

    out_file = Path(output_path)
    if out_file.exists() and not overwrite:
        return str(out_file)

    out_file.parent.mkdir(parents=True, exist_ok=True)

    min_lon, min_lat, max_lon, max_lat = bbox
    x0, y0 = deg2num(min_lat, min_lon, zoom)
    x1, y1 = deg2num(max_lat, max_lon, zoom)
    x0, x1 = sorted([x0, x1])
    y0, y1 = sorted([y0, y1])

    tile_min_x, tile_max_x = math.floor(x0), math.ceil(x1)
    tile_min_y, tile_max_y = math.floor(y0), math.ceil(y1)

    corners = list(itertools.product(range(tile_min_x, tile_max_x), range(tile_min_y, tile_max_y)))

    headers = {
        "User-Agent": "BhuDrishti-AI/1.0 (Geospatial Cadastral Mapping System)"
    }

    with httpx.Client(timeout=30.0, headers=headers, follow_redirects=True) as client:
        def fetch_single_tile(xy: tuple[int, int]) -> tuple[tuple[int, int], bytes | None]:
            x, y = xy
            url = source_url.format(z=zoom, x=x, y=y)
            for _ in range(3):
                try:
                    res = client.get(url)
                    if res.status_code == 200 and res.content:
                        return (xy, res.content)
                except Exception:
                    pass
            return (xy, None)

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            results = dict(executor.map(fetch_single_tile, corners))

    tile_w, tile_h = 256, 256
    full_w = max(tile_w, (tile_max_x - tile_min_x) * tile_w)
    full_h = max(tile_h, (tile_max_y - tile_min_y) * tile_h)
    stitched = Image.new("RGB", (full_w, full_h), color=(0, 0, 0))

    for (x, y), tile_bytes in results.items():
        if tile_bytes:
            try:
                tile_img = Image.open(io.BytesIO(tile_bytes)).convert("RGB")
                px = (x - tile_min_x) * tile_w
                py = (y - tile_min_y) * tile_h
                stitched.paste(tile_img, (px, py))
                tile_img.close()
            except Exception as e:
                logger.warning(f"Error parsing tile ({x}, {y}): {e}")

    # Crop to exact sub-tile bbox boundary
    x_frac_0 = x0 - tile_min_x
    y_frac_0 = y0 - tile_min_y
    crop_x0 = max(0, round(tile_w * x_frac_0))
    crop_y0 = max(0, round(tile_h * y_frac_0))
    crop_w = max(1, round(tile_w * (x1 - x0)))
    crop_h = max(1, round(tile_h * (y1 - y0)))

    cropped = stitched.crop((crop_x0, crop_y0, crop_x0 + crop_w, crop_y0 + crop_h))
    stitched.close()

    xp0, yp0 = from4326_to3857(min_lat, min_lon)
    xp1, yp1 = from4326_to3857(max_lat, max_lon)
    min_x_3857, max_x_3857 = sorted([xp0, xp1])
    min_y_3857, max_y_3857 = sorted([yp0, yp1])

    transform = from_bounds(min_x_3857, min_y_3857, max_x_3857, max_y_3857, cropped.width, cropped.height)
    arr = np.array(cropped)
    arr = np.transpose(arr, (2, 0, 1))

    with rasterio.open(
        str(out_file),
        "w",
        driver="GTiff",
        height=cropped.height,
        width=cropped.width,
        count=3,
        dtype="uint8",
        crs="EPSG:3857",
        transform=transform,
        compress="deflate",
    ) as dst:
        dst.write(arr)

    cropped.close()
    return str(out_file)

