"""Stable response contracts for v2 cadastral quality validation."""

from typing import Any

from pydantic import BaseModel, Field


class TopologyValidationFeature(BaseModel):
    index: int = Field(ge=0)
    valid: bool
    repaired: bool
    overlaps: int = Field(ge=0)
    overlap_area: float = Field(ge=0)
    near_duplicate: bool
    sliver: bool
    area: float = Field(ge=0)
    perimeter: float = Field(ge=0)
    cleaned_geometry: dict[str, Any]


class TopologyValidationResponse(BaseModel):
    type: str = "TopologyValidation"
    features: list[TopologyValidationFeature]
