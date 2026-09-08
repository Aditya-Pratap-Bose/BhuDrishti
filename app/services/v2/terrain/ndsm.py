"""
app/services/v2/terrain/ndsm.py
-------------------------------
Normalized Digital Surface Model (nDSM = DSM - DTM) computation and terrain metrics.
Provides surface height above ground for building extraction and vertical reasoning.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import numpy as np
import rasterio
from rasterio.errors import RasterioIOError
from rasterio.warp import Resampling, reproject

from app.core.exceptions import RasterValidationError


def compute_ndsm(
    dsm_path: str | Path,
    dtm_path: str | Path,
    output_path: str | Path | None = None,
) -> dict[str, Any]:
    """
    Compute normalized Digital Surface Model (nDSM = DSM - DTM).
    Normalizes elevation to height above ground level (AGL).
    """
    try:
        with rasterio.open(dsm_path) as dsm_ds, rasterio.open(dtm_path) as dtm_ds:
            if dsm_ds.crs != dtm_ds.crs:
                raise RasterValidationError("DSM and DTM must share the same Coordinate Reference System.")

            dsm_data = dsm_ds.read(1, masked=True)
            dtm_data = dtm_ds.read(1, masked=True)

            # If dimensions differ, reproject DTM to match DSM grid
            if dsm_data.shape != dtm_data.shape:
                resampled_dtm = np.empty_like(dsm_data, dtype=np.float32)
                reproject(
                    source=rasterio.band(dtm_ds, 1),
                    destination=resampled_dtm,
                    src_transform=dtm_ds.transform,
                    src_crs=dtm_ds.crs,
                    dst_transform=dsm_ds.transform,
                    dst_crs=dsm_ds.crs,
                    resampling=Resampling.bilinear,
                )
                dtm_array = np.ma.masked_invalid(resampled_dtm)
            else:
                dtm_array = dtm_data

            # Calculate nDSM = DSM - DTM
            ndsm_array = dsm_data - dtm_array
            # Clip negative noise (below bare ground) to 0
            ndsm_array = np.ma.clip(ndsm_array, 0.0, None)

            valid_mask = ~ndsm_array.mask & np.isfinite(ndsm_array.data)
            valid_values = ndsm_array.data[valid_mask]

            stats = {
                "min_height_m": float(np.min(valid_values)) if len(valid_values) > 0 else 0.0,
                "max_height_m": float(np.max(valid_values)) if len(valid_values) > 0 else 0.0,
                "mean_height_m": float(np.mean(valid_values)) if len(valid_values) > 0 else 0.0,
                "p95_height_m": float(np.percentile(valid_values, 95)) if len(valid_values) > 0 else 0.0,
            }

            if output_path:
                out_file = Path(output_path)
                out_file.parent.mkdir(parents=True, exist_ok=True)
                profile = dsm_ds.profile.copy()
                profile.update(
                    dtype=rasterio.float32,
                    count=1,
                    nodata=-9999.0,
                )
                filled_data = ndsm_array.filled(-9999.0).astype(np.float32)
                with rasterio.open(out_file, "w", **profile) as out_ds:
                    out_ds.write(filled_data, 1)

            return {
                "status": "success",
                "output_path": str(output_path) if output_path else None,
                "statistics": stats,
            }
    except RasterValidationError:
        raise
    except (RasterioIOError, OSError, ValueError) as exc:
        raise RasterValidationError(f"Could not compute nDSM from DSM and DTM: {exc}") from exc


def extract_building_height_mask(
    ndsm_raster: np.ndarray,
    min_height_m: float = 2.5,
    max_height_m: float = 60.0,
) -> np.ndarray:
    """
    Return binary mask where normalized surface elevation represents structures/buildings
    (typically 2.5m - 60m above ground).
    """
    values = np.asarray(ndsm_raster, dtype=np.float32)
    valid = np.isfinite(values) & (values >= 0)
    return valid & (values >= min_height_m) & (values <= max_height_m)


def compute_terrain_metrics(
    dtm_array: np.ndarray,
    cell_size_m: float = 1.0,
) -> dict[str, Any]:
    """
    Derive terrain slope (degrees), aspect (degrees from North), and terrain roughness.
    """
    elevation = np.asarray(dtm_array, dtype=np.float32)
    if elevation.ndim != 2 or min(elevation.shape) < 3:
        raise ValueError("DTM must be a 2D array of at least 3x3 dimensions.")

    cell_size = max(1e-6, float(cell_size_m))
    grad_y, grad_x = np.gradient(elevation, cell_size)
    slope_rad = np.arctan(np.hypot(grad_x, grad_y))
    slope_deg = np.degrees(slope_rad)

    aspect_rad = np.arctan2(-grad_x, grad_y)
    aspect_deg = (np.degrees(aspect_rad) + 360) % 360

    return {
        "mean_slope_deg": float(np.nanmean(slope_deg)),
        "max_slope_deg": float(np.nanmax(slope_deg)),
        "mean_aspect_deg": float(np.nanmean(aspect_deg)),
    }
