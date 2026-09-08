"""Authenticated v2 geometry quality and multidimensional evaluation endpoints."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from shapely.geometry import shape

from app.api.v1.auth import get_current_user
from app.models.user import User
from app.schemas.parcel import ParcelGeoJSONResponse
from app.schemas.quality import TopologyValidationResponse
from app.services.v2.quality.scorer import evaluate_cadastral_quality
from app.services.v2.topology import enforce_cadastral_topology, inspect_topology

router = APIRouter(prefix="/quality", tags=["v2 Quality"])


class QualityEvaluationRequest(BaseModel):
    raster_metadata: dict[str, Any] | None = None
    total_features: int = Field(..., ge=0)
    invalid_geometry_count: int = Field(default=0, ge=0)
    overlap_count: int = Field(default=0, ge=0)
    duplicate_count: int = Field(default=0, ge=0)
    sliver_count: int = Field(default=0, ge=0)
    mean_ai_confidence: float = Field(default=0.75, ge=0.0, le=1.0)
    reconciliation_summary: dict[str, int] | None = None


@router.post("/validate")
async def validate_parcels(
    payload: ParcelGeoJSONResponse,
    current_user: User = Depends(get_current_user),
) -> TopologyValidationResponse:
    """Return quality flags and cleaned GeoJSON without persisting changes."""
    del current_user
    geometries = [shape(feature.geometry.model_dump()) for feature in payload.features]
    results = []
    for index, geometry in enumerate(geometries):
        neighbours = geometries[:index] + geometries[index + 1 :]
        try:
            cleaned = enforce_cadastral_topology(geometry, neighbours)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        report = inspect_topology(geometry, neighbours)
        results.append(
            {
                "index": index,
                "valid": report.valid,
                "repaired": report.repaired,
                "overlaps": report.overlaps,
                "overlap_area": report.overlap_area,
                "near_duplicate": report.near_duplicate,
                "sliver": report.sliver,
                "area": report.area,
                "perimeter": report.perimeter,
                "cleaned_geometry": cleaned.__geo_interface__,
            }
        )
    return TopologyValidationResponse(type="TopologyValidation", features=results)


@router.post("/report")
def generate_quality_report(
    payload: QualityEvaluationRequest,
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Generate a multidimensional quality report across raster, geometry, topology, AI, and reconciliation."""
    del current_user
    report = evaluate_cadastral_quality(
        raster_meta=payload.raster_metadata,
        total_features=payload.total_features,
        invalid_geometry_count=payload.invalid_geometry_count,
        overlap_count=payload.overlap_count,
        duplicate_count=payload.duplicate_count,
        sliver_count=payload.sliver_count,
        mean_ai_confidence=payload.mean_ai_confidence,
        reconciliation_summary=payload.reconciliation_summary,
    )
    return report.to_dict()
