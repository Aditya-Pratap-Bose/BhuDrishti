import tempfile
import unittest
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_origin

from app.services.v2.feature_extraction import extract_features


class V2FeatureExtractionTests(unittest.TestCase):
    def test_extracts_reviewable_polygons_from_raster(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "asset.tif"
            values = np.array(
                [[1, 1, 1, 1], [1, 9, 9, 1], [1, 9, 9, 1], [1, 1, 1, 1]],
                dtype=np.float32,
            )
            with rasterio.open(
                path,
                "w",
                driver="GTiff",
                width=4,
                height=4,
                count=1,
                dtype="float32",
                crs="EPSG:32643",
                transform=from_origin(0, 4, 1, 1),
            ) as dataset:
                dataset.write(values, 1)

            features = extract_features(path, "building", 75)

            self.assertEqual(len(features), 1)
            self.assertEqual(features[0]["properties"]["layer"], "building")
            self.assertGreater(features[0]["properties"]["area"], 0)


if __name__ == "__main__":
    unittest.main()
