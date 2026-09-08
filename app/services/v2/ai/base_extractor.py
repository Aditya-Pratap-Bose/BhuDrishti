"""
app/services/v2/ai/base_extractor.py
------------------------------------
Abstract interface and provenance models for BhuDrishti V2 AI feature extractors.
"""

from __future__ import annotations

import abc
import enum
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class FeatureLayerType(str, enum.Enum):
    PARCEL = "parcel"
    BUILDING = "building"
    ROAD = "road"
    ACCESS_CORRIDOR = "access_corridor"
    LAND_USE = "land_use"


class LandUseCategory(str, enum.Enum):
    RESIDENTIAL = "RESIDENTIAL"
    COMMERCIAL = "COMMERCIAL"
    INDUSTRIAL = "INDUSTRIAL"
    INSTITUTIONAL = "INSTITUTIONAL"
    AGRICULTURAL = "AGRICULTURAL"
    TRANSPORTATION = "TRANSPORTATION"
    VACANT = "VACANT"
    MIXED = "MIXED"
    OTHER = "OTHER"
    UNKNOWN = "UNKNOWN"


@dataclass
class ExtractionProvenance:
    model_name: str
    model_version: str
    framework: str
    source_asset_id: str
    processing_run_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    parameters: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExtractedFeature:
    geometry: dict[str, Any]
    properties: dict[str, Any]
    layer: FeatureLayerType
    confidence: float
    provenance: ExtractionProvenance


@dataclass
class ExtractionResult:
    layer: FeatureLayerType
    features: list[ExtractedFeature]
    provenance: ExtractionProvenance
    summary: dict[str, Any] = field(default_factory=dict)

    def to_geojson(self) -> dict[str, Any]:
        """Convert extracted features into a standard GeoJSON FeatureCollection."""
        return {
            "type": "FeatureCollection",
            "properties": {
                "layer": self.layer.value,
                "model_name": self.provenance.model_name,
                "model_version": self.provenance.model_version,
                "processing_run_id": self.provenance.processing_run_id,
                "created_at": self.provenance.created_at,
                "feature_count": len(self.features),
                "summary": self.summary,
            },
            "features": [
                {
                    "type": "Feature",
                    "geometry": f.geometry,
                    "properties": {
                        **f.properties,
                        "layer": f.layer.value,
                        "confidence": round(f.confidence, 4),
                        "model_name": f.provenance.model_name,
                        "model_version": f.provenance.model_version,
                        "processing_run_id": f.provenance.processing_run_id,
                    },
                }
                for f in self.features
            ],
        }


class BaseFeatureExtractor(abc.ABC):
    """Abstract interface that all specialized cadastral AI extractors must implement."""

    layer_type: FeatureLayerType
    model_name: str
    model_version: str
    framework: str

    @abc.abstractmethod
    def extract(
        self,
        asset_path: str | Path,
        **kwargs: Any,
    ) -> ExtractionResult:
        """Run feature extraction on input raster/data asset with full provenance."""
