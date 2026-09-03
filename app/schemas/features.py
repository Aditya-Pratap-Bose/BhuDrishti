"""Versioned contracts for PS 26012 cadastral feature outputs."""

from typing import Literal

from pydantic import BaseModel, Field


FeatureLayer = Literal["parcel", "building", "road", "access_corridor", "land_use"]
ReviewState = Literal["draft", "needs_review", "verified", "rejected"]


class ConfidenceMetadata(BaseModel):
    score: float = Field(ge=0.0, le=1.0)
    model_name: str
    model_version: str


class GroundTruthEvidence(BaseModel):
    source: Literal["gnss_cors", "field_survey", "existing_gis", "operator"]
    reference_id: str | None = None
    notes: str | None = None


class CadastralFeatureContract(BaseModel):
    layer: FeatureLayer
    review_state: ReviewState = "draft"
    confidence: ConfidenceMetadata | None = None
    ground_truth: GroundTruthEvidence | None = None


class FeatureExtractionRequest(BaseModel):
    asset_id: str = Field(min_length=1, max_length=255)
    layer: Literal["building", "road", "access_corridor", "land_use"]
    threshold_percentile: float = Field(default=75.0, ge=1.0, le=99.0)


class ExtractedFeature(BaseModel):
    type: Literal["Feature"] = "Feature"
    geometry: dict
    properties: dict


class FeatureExtractionResponse(BaseModel):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    layer: FeatureLayer
    source_asset_id: str
    model: str
    features: list[ExtractedFeature]


class V2Capability(BaseModel):
    layer: FeatureLayer
    status: Literal["available", "planned"]
    description: str


class V2CapabilityManifest(BaseModel):
    api_version: Literal["v2"] = "v2"
    problem_statement: str = "SIH 26012"
    capabilities: list[V2Capability]
