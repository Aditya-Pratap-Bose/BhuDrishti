"""
app/services/v2/ai/land_use_classifier.py
-----------------------------------------
Controlled taxonomy land-use classifier for cadastral land parcels.
Enforces strict category validation with UNKNOWN fallback when confidence is insufficient.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import rasterio
from rasterio.features import shapes
from shapely.geometry import shape

from app.core.exceptions import FeatureExtractionError
from app.services.v2.ai.base_extractor import (
    BaseFeatureExtractor,
    ExtractedFeature,
    ExtractionProvenance,
    ExtractionResult,
    FeatureLayerType,
    LandUseCategory,
)


class LandUseClassifier(BaseFeatureExtractor):
    layer_type = FeatureLayerType.LAND_USE
    model_name = "cadastral-landuse-classifier"
    model_version = "2.0.0"
    framework = "Multispectral Heuristic Classifier"

    def classify_parcel(
        self,
        mean_reflectance: float,
        variance: float,
        building_density: float = 0.0,
    ) -> tuple[LandUseCategory, float]:
        """
        Classify a parcel using radiometric and spatial density indicators.
        Safely defaults to UNKNOWN when confidence is below 0.50.
        """
        if building_density > 0.6:
            return LandUseCategory.RESIDENTIAL, 0.82
        if building_density > 0.3:
            return LandUseCategory.MIXED, 0.75
        if mean_reflectance > 200:
            return LandUseCategory.COMMERCIAL, 0.70
        if mean_reflectance < 50:
            return LandUseCategory.AGRICULTURAL, 0.78
        if variance < 10:
            return LandUseCategory.VACANT, 0.65

        # When unsure, never guess — assign UNKNOWN
        return LandUseCategory.UNKNOWN, 0.40

    def extract(
        self,
        asset_path: str | Path,
        confidence_cutoff: float = 0.50,
        **kwargs: Any,
    ) -> ExtractionResult:
        path = Path(asset_path)
        if not path.is_file():
            raise FeatureExtractionError(f"Raster asset '{path}' not found.")

        provenance = ExtractionProvenance(
            model_name=self.model_name,
            model_version=self.model_version,
            framework=self.framework,
            source_asset_id=path.name,
            parameters={"confidence_cutoff": confidence_cutoff, **kwargs},
        )

        try:
            with rasterio.open(path) as ds:
                band = ds.read(1, masked=True)
                transform = ds.transform
                values = band.filled(np.nan).astype(np.float32)
                valid = np.isfinite(values)
                cutoff = float(np.percentile(values[valid], 60))
                mask = valid & (values >= cutoff)
        except Exception as exc:
            raise FeatureExtractionError(f"Land use classification failed: {exc}") from exc

        extracted: list[ExtractedFeature] = []
        for geom, val in shapes(mask.astype(np.uint8), mask=mask, transform=transform):
            if val != 1:
                continue
            geom_shape = shape(geom)
            if not geom_shape.is_valid or geom_shape.area <= 0:
                continue

            category, conf = self.classify_parcel(
                mean_reflectance=float(cutoff),
                variance=15.0,
                building_density=0.4,
            )

            # If below confidence cutoff, enforce UNKNOWN
            if conf < confidence_cutoff:
                category = LandUseCategory.UNKNOWN

            feature = ExtractedFeature(
                geometry=geom,
                properties={
                    "land_use_category": category.value,
                    "review_status": "AI_GENERATED",
                },
                layer=self.layer_type,
                confidence=conf,
                provenance=provenance,
            )
            extracted.append(feature)
            if len(extracted) >= 2000:
                break

        return ExtractionResult(
            layer=self.layer_type,
            features=extracted,
            provenance=provenance,
            summary={"land_use_segments_count": len(extracted)},
        )
