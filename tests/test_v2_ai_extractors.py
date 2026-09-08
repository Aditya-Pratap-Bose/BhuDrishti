"""
tests/test_v2_ai_extractors.py
------------------------------
Unit tests for V2 AI feature extractors and model registry.
"""

import tempfile
import unittest
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_origin

from app.services.v2.ai import (
    AccessCorridorExtractor,
    BuildingExtractor,
    FeatureLayerType,
    LandUseCategory,
    LandUseClassifier,
    ModelRegistry,
    ParcelExtractor,
    RoadExtractor,
)


class V2AIExtractorsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.raster_path = Path(self.temp_dir.name) / "test_ori.tif"
        values = np.arange(100, dtype=np.float32).reshape((10, 10))
        with rasterio.open(
            self.raster_path,
            "w",
            driver="GTiff",
            width=10,
            height=10,
            count=1,
            dtype="float32",
            crs="EPSG:32643",
            transform=from_origin(100.0, 200.0, 1.0, 1.0),
        ) as ds:
            ds.write(values, 1)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_model_registry_discovery(self) -> None:
        models = ModelRegistry.list_models()
        self.assertGreaterEqual(len(models), 5)
        layers = [m["layer"] for m in models]
        self.assertIn("parcel", layers)
        self.assertIn("building", layers)
        self.assertIn("road", layers)
        self.assertIn("access_corridor", layers)
        self.assertIn("land_use", layers)

    def test_parcel_extractor_execution(self) -> None:
        extractor = ModelRegistry.get_extractor(FeatureLayerType.PARCEL)
        self.assertIsInstance(extractor, ParcelExtractor)
        result = extractor.extract(self.raster_path)
        self.assertEqual(result.layer, FeatureLayerType.PARCEL)
        geojson = result.to_geojson()
        self.assertEqual(geojson["type"], "FeatureCollection")
        self.assertEqual(geojson["properties"]["model_name"], "sam-vit-b-cadastral")

    def test_building_extractor_with_ndsm(self) -> None:
        extractor = ModelRegistry.get_extractor("building")
        self.assertIsInstance(extractor, BuildingExtractor)
        result = extractor.extract(self.raster_path)
        self.assertEqual(result.layer, FeatureLayerType.BUILDING)
        for f in result.features:
            self.assertIn("building_id", f.properties)
            self.assertGreater(f.confidence, 0.5)

    def test_road_extractor_execution(self) -> None:
        extractor = ModelRegistry.get_extractor("road")
        self.assertIsInstance(extractor, RoadExtractor)
        result = extractor.extract(self.raster_path)
        self.assertEqual(result.layer, FeatureLayerType.ROAD)
        for f in result.features:
            self.assertIn("road_id", f.properties)

    def test_access_corridor_extractor_execution(self) -> None:
        extractor = ModelRegistry.get_extractor("access_corridor")
        self.assertIsInstance(extractor, AccessCorridorExtractor)
        result = extractor.extract(self.raster_path)
        self.assertEqual(result.layer, FeatureLayerType.ACCESS_CORRIDOR)

    def test_land_use_classifier_controlled_taxonomy(self) -> None:
        classifier = LandUseClassifier()
        # High building density -> RESIDENTIAL
        cat, conf = classifier.classify_parcel(mean_reflectance=120, variance=20, building_density=0.7)
        self.assertEqual(cat, LandUseCategory.RESIDENTIAL)

        # Low confidence -> UNKNOWN
        cat_unknown, conf_unknown = classifier.classify_parcel(mean_reflectance=100, variance=25, building_density=0.1)
        self.assertEqual(cat_unknown, LandUseCategory.UNKNOWN)


if __name__ == "__main__":
    unittest.main()
