"""
app/services/v2/ai/building_extractor.py
----------------------------------------
Building footprint candidate extractor.
Correlates optical imagery with optional surface elevation (DSM/DTM or nDSM)
to extract roof footprints and vertical height attributes.
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


class BuildingExtractor(BaseFeatureExtractor):
    layer_type = FeatureLayerType.BUILDING
    model_name = "cadastral-building-height-extractor"
    model_version = "2.0.0"
    framework = "Computer Vision + Terrain nDSM"

    def extract(
        self,
        asset_path: str | Path,
        ndsm_path: str | Path | None = None,
        min_building_height_m: float = 2.5,
        min_area_sqm: float = 12.0,
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
            parameters={
                "ndsm_used": bool(ndsm_path),
                "min_building_height_m": min_building_height_m,
                "min_area_sqm": min_area_sqm,
                **kwargs,
            },
        )

        try:
            with rasterio.open(path) as ds:
                band = ds.read(1, masked=True)
                transform = ds.transform
                crs = ds.crs.to_string() if ds.crs else None
                values = band.filled(np.nan).astype(np.float32)
                valid = np.isfinite(values)

                # If nDSM is provided, use elevation height >= min_building_height_m
                if ndsm_path and Path(ndsm_path).is_file():
                    with rasterio.open(ndsm_path) as ndsm_ds:
                        ndsm_values = ndsm_ds.read(1)
                        mask = valid & (ndsm_values >= min_building_height_m)
                        has_height = True
                else:
                    # Optical brightness/contrast thresholding
                    cutoff = float(np.percentile(values[valid], 75))
                    mask = valid & (values >= cutoff)
                    has_height = False
                    ndsm_values = None
        except Exception as exc:
            raise FeatureExtractionError(f"Building extraction failed on raster: {exc}") from exc

        extracted: list[ExtractedFeature] = []
        for geom, val in shapes(mask.astype(np.uint8), mask=mask, transform=transform):
            if val != 1:
                continue
            geom_shape = shape(geom)
            if not geom_shape.is_valid:
                continue
            area = geom_shape.area
            if area < (min_area_sqm if crs and "326" in crs else min_area_sqm * 1e-10):
                continue

            properties: dict[str, Any] = {
                "building_id": f"BLD-{uuid.uuid4().hex[:8].upper()}",
                "area_sqm": round(area, 2),
                "has_height_data": has_height,
                "review_status": "AI_GENERATED",
            }
            if has_height and ndsm_values is not None:
                properties["estimated_height_m"] = round(float(np.nanmax(ndsm_values)), 1)

            feature = ExtractedFeature(
                geometry=geom,
                properties=properties,
                layer=self.layer_type,
                confidence=0.85 if has_height else 0.70,
                provenance=provenance,
            )
            extracted.append(feature)
            if len(extracted) >= 5000:
                break

        return ExtractionResult(
            layer=self.layer_type,
            features=extracted,
            provenance=provenance,
            summary={"building_count": len(extracted), "has_height": has_height},
        )
