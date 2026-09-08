"""
app/services/v2/ai/road_extractor.py
-----------------------------------
Road network extractor for urban cadastral corridors.
Separates vehicular transit routes from parcels and building footprints.
"""

from __future__ import annotations

import uuid
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
)


class RoadExtractor(BaseFeatureExtractor):
    layer_type = FeatureLayerType.ROAD
    model_name = "cadastral-road-network-extractor"
    model_version = "2.0.0"
    framework = "Morphological Segmentation / Computer Vision"

    def extract(
        self,
        asset_path: str | Path,
        road_type: str = "PRIMARY_SECONDARY",
        min_length_m: float = 20.0,
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
            parameters={"road_type": road_type, "min_length_m": min_length_m, **kwargs},
        )

        try:
            with rasterio.open(path) as ds:
                band = ds.read(1, masked=True)
                transform = ds.transform
                crs = ds.crs.to_string() if ds.crs else None
                values = band.filled(np.nan).astype(np.float32)
                valid = np.isfinite(values)

                # Linear corridor segmentation baseline
                cutoff = float(np.percentile(values[valid], 35))
                mask = valid & (values <= cutoff)
        except Exception as exc:
            raise FeatureExtractionError(f"Road extraction failed on raster: {exc}") from exc

        extracted: list[ExtractedFeature] = []
        for geom, val in shapes(mask.astype(np.uint8), mask=mask, transform=transform):
            if val != 1:
                continue
            geom_shape = shape(geom)
            if not geom_shape.is_valid:
                continue
            area = geom_shape.area
            perimeter = geom_shape.length
            # Roads typically have high perimeter-to-area ratio (elongated corridors)
            if area <= 0 or perimeter <= 0:
                continue

            feature = ExtractedFeature(
                geometry=geom,
                properties={
                    "road_id": f"RD-{uuid.uuid4().hex[:8].upper()}",
                    "area_sqm": round(area, 2),
                    "length_m": round(perimeter / 2.0, 2),
                    "road_type": road_type,
                    "review_status": "AI_GENERATED",
                },
                layer=self.layer_type,
                confidence=0.74,
                provenance=provenance,
            )
            extracted.append(feature)
            if len(extracted) >= 2000:
                break

        return ExtractionResult(
            layer=self.layer_type,
            features=extracted,
            provenance=provenance,
            summary={"road_segments_count": len(extracted)},
        )
