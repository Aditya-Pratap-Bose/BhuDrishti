"""
app/services/v2/ai/model_registry.py
-----------------------------------
Central registry for BhuDrishti V2 cadastral AI models and feature extractors.
Ensures full auditability, reproducibility, and version tracking.
"""

from __future__ import annotations

from typing import Any

from app.core.exceptions import FeatureExtractionError
from app.services.v2.ai.access_corridor_extractor import AccessCorridorExtractor
from app.services.v2.ai.base_extractor import BaseFeatureExtractor, FeatureLayerType
from app.services.v2.ai.building_extractor import BuildingExtractor
from app.services.v2.ai.land_use_classifier import LandUseClassifier
from app.services.v2.ai.parcel_extractor import ParcelExtractor
from app.services.v2.ai.road_extractor import RoadExtractor

_EXTRACTORS: dict[FeatureLayerType, type[BaseFeatureExtractor]] = {
    FeatureLayerType.PARCEL: ParcelExtractor,
    FeatureLayerType.BUILDING: BuildingExtractor,
    FeatureLayerType.ROAD: RoadExtractor,
    FeatureLayerType.ACCESS_CORRIDOR: AccessCorridorExtractor,
    FeatureLayerType.LAND_USE: LandUseClassifier,
}


class ModelRegistry:
    @classmethod
    def get_extractor(cls, layer: str | FeatureLayerType) -> BaseFeatureExtractor:
        """Instantiate the registered extractor for a given cadastral layer."""
        try:
            layer_enum = FeatureLayerType(layer)
        except ValueError:
            raise FeatureExtractionError(f"Unsupported feature layer: '{layer}'.")

        extractor_cls = _EXTRACTORS.get(layer_enum)
        if not extractor_cls:
            raise FeatureExtractionError(f"No extractor registered for layer '{layer_enum.value}'.")
        return extractor_cls()

    @classmethod
    def list_models(cls) -> list[dict[str, Any]]:
        """Return catalog of available AI models and their capabilities."""
        models = []
        for layer_type, extractor_cls in _EXTRACTORS.items():
            models.append(
                {
                    "layer": layer_type.value,
                    "model_name": extractor_cls.model_name,
                    "model_version": extractor_cls.model_version,
                    "framework": extractor_cls.framework,
                }
            )
        return models
