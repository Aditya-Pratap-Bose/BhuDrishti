"""
app/api/v2/exports.py
---------------------
Authenticated endpoints for generating government-compliant cadastral export packages.
Supports GeoJSON, CSV tabular summaries, and official NAKSHA / DoLR validation-gated packages.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field

from app.api.v1.auth import get_current_user
from app.models.user import User
from app.services.v2.exports import (
    export_to_csv,
    export_to_geojson,
    generate_naksha_export_package,
)

logger = logging.getLogger("bhudrishti.api.v2.exports")

router = APIRouter(prefix="/exports", tags=["v2 Cadastral Exports"])


class GenericExportRequest(BaseModel):
    features: list[dict[str, Any]] = Field(..., description="List of GeoJSON Feature objects")
    crs: str = "EPSG:32643"
    metadata: dict[str, Any] | None = None


class NakshaPackageRequest(BaseModel):
    project_metadata: dict[str, Any] = Field(..., description="Project name, state, district, ULB")
    survey_unit: str = Field(..., min_length=2, max_length=64)
    features: list[dict[str, Any]] = Field(..., description="Validated cadastral features")
    crs: str = "EPSG:32643"
    unresolved_topology_errors: int = Field(default=0, ge=0)
    model_version: str = "2.0.0"


@router.post("/geojson")
def export_layer_geojson(
    payload: GenericExportRequest,
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Export features as a standardized GeoJSON FeatureCollection."""
    del current_user
    return export_to_geojson(
        features=payload.features,
        crs=payload.crs,
        metadata=payload.metadata,
    )


@router.post("/csv", response_class=Response)
def export_layer_csv(
    payload: GenericExportRequest,
    current_user: User = Depends(get_current_user),
) -> Response:
    """Export feature attributes as a CSV table for land revenue registers."""
    del current_user
    csv_str = export_to_csv(payload.features)
    return Response(
        content=csv_str,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=cadastral_records.csv"},
    )


@router.post("/naksha-package")
def export_naksha_package(
    payload: NakshaPackageRequest,
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Generate an official NAKSHA export package with pre-flight validation gating.
    Returns status READY with manifest and SHA256 checksum, or BLOCKED with specific audit reasons.
    """
    del current_user
    result = generate_naksha_export_package(
        project_meta=payload.project_metadata,
        survey_unit=payload.survey_unit,
        features=payload.features,
        crs=payload.crs,
        unresolved_topology_errors=payload.unresolved_topology_errors,
        model_version=payload.model_version,
    )
    return result
