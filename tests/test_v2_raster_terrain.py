"""
tests/test_v2_raster_terrain.py
-------------------------------
Unit tests for V2 raster inspection, trio co-registration, and terrain/nDSM analysis.
"""

import tempfile
import unittest
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_origin

from app.core.exceptions import RasterValidationError
from app.services.v2.raster import (
    convert_to_cog,
    inspect_raster,
    validate_coregistration,
    validate_trio_coregistration,
)
from app.services.v2.terrain.ndsm import (
    compute_ndsm,
    compute_terrain_metrics,
    extract_building_height_mask,
)


class V2RasterTerrainTests(unittest.TestCase):
    def test_inspect_raster_includes_gsd_and_nodata(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "test.tif"
            with rasterio.open(
                path,
                "w",
                driver="GTiff",
                width=20,
                height=20,
                count=1,
                dtype="float32",
                crs="EPSG:32643",
                nodata=-9999.0,
                transform=from_origin(100.0, 200.0, 0.25, 0.25),
            ) as ds:
                ds.write(np.ones((20, 20), dtype=np.float32), 1)

            meta = inspect_raster(path)
            self.assertEqual(meta["width"], 20)
            self.assertEqual(meta["height"], 20)
            self.assertEqual(meta["nodata"], -9999.0)
            self.assertAlmostEqual(meta["gsd"], 0.25)

    def test_validate_trio_coregistration_success(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            dir_path = Path(temp_dir)
            ori_path = dir_path / "ori.tif"
            dsm_path = dir_path / "dsm.tif"
            dtm_path = dir_path / "dtm.tif"

            # Create overlapping rasters in EPSG:32643
            for p in [ori_path, dsm_path, dtm_path]:
                with rasterio.open(
                    p,
                    "w",
                    driver="GTiff",
                    width=10,
                    height=10,
                    count=1,
                    dtype="float32",
                    crs="EPSG:32643",
                    transform=from_origin(500000.0, 2300000.0, 0.5, 0.5),
                ) as ds:
                    ds.write(np.ones((10, 10), dtype=np.float32), 1)

            result = validate_trio_coregistration(ori_path, dsm_path, dtm_path)
            self.assertTrue(result["valid"])
            self.assertEqual(result["crs"], "EPSG:32643")

    def test_validate_trio_coregistration_crs_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            dir_path = Path(temp_dir)
            ori_path = dir_path / "ori.tif"
            dsm_path = dir_path / "dsm.tif"
            dtm_path = dir_path / "dtm.tif"

            with rasterio.open(
                ori_path, "w", driver="GTiff", width=10, height=10, count=1, dtype="float32",
                crs="EPSG:32643", transform=from_origin(0, 10, 1, 1)
            ) as ds:
                ds.write(np.ones((10, 10), dtype=np.float32), 1)

            with rasterio.open(
                dsm_path, "w", driver="GTiff", width=10, height=10, count=1, dtype="float32",
                crs="EPSG:32643", transform=from_origin(0, 10, 1, 1)
            ) as ds:
                ds.write(np.ones((10, 10), dtype=np.float32), 1)

            # Different CRS
            with rasterio.open(
                dtm_path, "w", driver="GTiff", width=10, height=10, count=1, dtype="float32",
                crs="EPSG:4326", transform=from_origin(0, 10, 1, 1)
            ) as ds:
                ds.write(np.ones((10, 10), dtype=np.float32), 1)

            with self.assertRaises(RasterValidationError):
                validate_trio_coregistration(ori_path, dsm_path, dtm_path)

    def test_ndsm_computation_and_building_height(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            dir_path = Path(temp_dir)
            dsm_path = dir_path / "dsm.tif"
            dtm_path = dir_path / "dtm.tif"
            ndsm_out = dir_path / "ndsm.tif"

            # Bare earth terrain at elevation 100m
            dtm_data = np.full((10, 10), 100.0, dtype=np.float32)
            # Surface has ground at 100m, building of 12m height in center (112m elevation)
            dsm_data = dtm_data.copy()
            dsm_data[3:7, 3:7] = 112.0

            for p, data in [(dsm_path, dsm_data), (dtm_path, dtm_data)]:
                with rasterio.open(
                    p, "w", driver="GTiff", width=10, height=10, count=1, dtype="float32",
                    crs="EPSG:32643", transform=from_origin(0, 10, 1, 1)
                ) as ds:
                    ds.write(data, 1)

            result = compute_ndsm(dsm_path, dtm_path, ndsm_out)
            self.assertEqual(result["status"], "success")
            self.assertAlmostEqual(result["statistics"]["max_height_m"], 12.0)
            self.assertAlmostEqual(result["statistics"]["min_height_m"], 0.0)

            # Verify building candidate mask
            with rasterio.open(ndsm_out) as ds:
                ndsm_read = ds.read(1)
            bldg_mask = extract_building_height_mask(ndsm_read, min_height_m=3.0, max_height_m=50.0)
            self.assertEqual(int(np.sum(bldg_mask)), 16)  # 4x4 area = 16 pixels

    def test_terrain_metrics_slope_and_aspect(self) -> None:
        # Elevation increases East, so the downhill slope faces West (270 degrees)
        dtm_sloped = np.array([
            [10.0, 11.0, 12.0],
            [10.0, 11.0, 12.0],
            [10.0, 11.0, 12.0],
        ], dtype=np.float32)
        metrics = compute_terrain_metrics(dtm_sloped, cell_size_m=1.0)
        self.assertGreater(metrics["mean_slope_deg"], 0)
        self.assertAlmostEqual(metrics["mean_aspect_deg"], 270.0, delta=5.0)


if __name__ == "__main__":
    unittest.main()
