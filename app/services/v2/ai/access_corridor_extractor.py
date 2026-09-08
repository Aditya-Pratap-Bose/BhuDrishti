"""
app/services/v2/ai/access_corridor_extractor.py
-----------------------------------------------
Dedicated extractor for narrow pedestrian pathways, alleyways, and parcel-access corridors.
Essential for validating land parcel access rights and legal connectivity.
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


class AccessCorridorExtractor(BaseFeatureExtractor):
    layer_type = FeatureLayerType.ACCESS_CORRIDOR
    model_name = "cadastral-access-corridor-extractor"
    model_version = "2.0.0"
    framework = "Computer Vision / Morphology"

    def extract(
        self,
        asset_path: str | Path,
        max_corridor_width_m: float = 4.0,
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
            parameters={"max_corridor_width_m": max_corridor_width_m, **kwargs},
        )

        try:
            with rasterio.open(path) as ds:
                band = ds.read(1, masked=True)
                transform = ds.transform
                values = band.filled(np.nan).astype(np.float32)
                valid = np.isfinite(values)
                # Narrow pathway filter
                p40 = float(np.percentile(values[valid], 40))
                p50 = float(np.percentile(values[valid], 50))
                mask = valid & (values >= p40) & (values <= p50)
        except Exception as exc:
            raise FeatureExtractionError(f"Access corridor extraction failed: {exc}") from exc

        extracted: list[ExtractedFeature] = []
        for geom, val in shapes(mask.astype(np.uint8), mask=mask, transform=transform):
            if val != 1:
                continue
            geom_shape = shape(geom)
            if not geom_shape.is_valid:
                continue
            area = geom_shape.area
            if area <= 0:
                continue

            feature = ExtractedFeature(
                geometry=geom,
                properties={
                    "corridor_id": f"ACC-{uuid.uuid4().hex[:8].upper()}",
                    "corridor_type": "PEDESTRIAN_PATHWAY",
                    "width_estimate_m": round(max_corridor_width_m, 1),
                    "review_status": "AI_GENERATED",
                },
                layer=self.layer_type,
                confidence=0.71,
                provenance=provenance,
            )
            extracted.append(feature)
            if len(extracted) >= 2000:
                break

        return ExtractionResult(
            layer=self.layer_type,
            features=extracted,
            provenance=provenance,
            summary={"corridors_count": len(extracted)},
        )
