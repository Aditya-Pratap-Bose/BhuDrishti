"""Backend raster validation and Cloud Optimized GeoTIFF preparation."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import rasterio
from rasterio.errors import RasterioIOError
from rasterio.shutil import copy as rio_copy


class RasterValidationError(ValueError):
    """Raised when a raster cannot be used by the v2 pipeline."""


def inspect_raster(path: str | Path) -> dict[str, Any]:
    try:
        with rasterio.open(path) as dataset:
            if dataset.driver not in {"GTiff", "COG"}:
                raise RasterValidationError("Raster must be a GeoTIFF file.")
            if dataset.crs is None:
                raise RasterValidationError("Raster must contain a coordinate reference system.")
            if dataset.width < 1 or dataset.height < 1 or dataset.count < 1:
                raise RasterValidationError("Raster dimensions and band count must be positive.")
            bounds = dataset.bounds
            values = (
                bounds.left,
                bounds.bottom,
                bounds.right,
                bounds.top,
                dataset.res[0],
                dataset.res[1],
            )
            if not all(math.isfinite(float(value)) for value in values):
                raise RasterValidationError("Raster bounds and resolution must be finite.")
            return {
                "width": dataset.width,
                "height": dataset.height,
                "bands": dataset.count,
                "dtype": dataset.dtypes[0],
                "crs": dataset.crs.to_string(),
                "bounds": [bounds.left, bounds.bottom, bounds.right, bounds.top],
                "resolution": [dataset.res[0], dataset.res[1]],
            }
    except RasterValidationError:
        raise
    except (RasterioIOError, ValueError, OSError) as exc:
        raise RasterValidationError(
            "The uploaded file is not a readable GeoTIFF raster."
        ) from exc


def validate_coregistration(ori_path: str | Path, dtm_path: str | Path) -> None:
    # Inspect first so malformed files get the same actionable error as
    # standalone raster validation.
    inspect_raster(ori_path)
    inspect_raster(dtm_path)
    try:
        with rasterio.open(ori_path) as ori, rasterio.open(dtm_path) as dtm:
            if ori.crs != dtm.crs:
                raise RasterValidationError("ORI and DTM must use the same CRS.")
            if (
                ori.bounds.right <= dtm.bounds.left
                or dtm.bounds.right <= ori.bounds.left
                or ori.bounds.top <= dtm.bounds.bottom
                or dtm.bounds.top <= ori.bounds.bottom
            ):
                raise RasterValidationError("ORI and DTM do not overlap spatially.")
    except RasterValidationError:
        raise
    except (RasterioIOError, ValueError, OSError) as exc:
        raise RasterValidationError(
            "ORI and DTM could not be opened for co-registration validation."
        ) from exc


def convert_to_cog(source_path: str | Path, output_path: str | Path) -> str:
    """Convert a validated GeoTIFF to a tiled, compressed COG-compatible GeoTIFF."""
    inspect_raster(source_path)
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        rio_copy(
            str(source_path),
            str(destination),
            driver="COG",
            compress="deflate",
            blocksize=512,
            overview_resampling="average",
        )
    except (RasterioIOError, ValueError, OSError) as exc:
        destination.unlink(missing_ok=True)
        raise RasterValidationError("Raster could not be converted to a COG.") from exc
    return str(destination)
