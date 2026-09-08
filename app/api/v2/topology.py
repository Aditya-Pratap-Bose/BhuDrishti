"""
app/api/v2/topology.py
----------------------
Authenticated endpoints for comprehensive cadastral topology and cross-layer validation.
Generates structured audit issues (overlaps, gaps, slivers, encroachments).
"""

from __future__ import annotations

import uuid
import logging
from typing import Any

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field

from app.api.v1.auth import get_current_user
from app.models.user import User
from app.schemas.v2.validation import ValidationIssueCreate
from app.services.v2.topology.engine import CadastralTopologyEngine

logger = logging.getLogger("bhudrishti.api.v2.topology")

router = APIRouter(prefix="/topology", tags=["v2 Cadastral Topology"])


class ParcelTopologyCheckRequest(BaseModel):
    project_id: uuid.UUID
    dataset_id: uuid.UUID | None = None
    parcels: list[dict[str, Any]] = Field(..., description="List of GeoJSON Feature objects")
    min_area_sqm: float = 5.0


class CrossLayerCheckRequest(BaseModel):
    project_id: uuid.UUID
    dataset_id: uuid.UUID | None = None
    parcels: list[dict[str, Any]] = Field(..., description="List of GeoJSON parcel features")
    buildings: list[dict[str, Any]] = Field(..., description="List of GeoJSON building features")


class TopologyValidationReport(BaseModel):
    is_valid: bool
    total_issues: int
    critical_count: int
    error_count: int
    warning_count: int
    issues: list[ValidationIssueCreate]


@router.post("/validate-parcels", response_model=TopologyValidationReport)
def validate_parcel_topology(
    payload: ParcelTopologyCheckRequest,
    current_user: User = Depends(get_current_user),
) -> TopologyValidationReport:
    """Validate parcel boundaries for overlaps, self-intersections, duplicates, and slivers."""
    del current_user
    engine = CadastralTopologyEngine()
    issues = engine.validate_parcels(
        parcels=payload.parcels,
        project_id=payload.project_id,
        dataset_id=payload.dataset_id,
        min_area_sqm=payload.min_area_sqm,
    )
    criticals = sum(1 for i in issues if i.severity == "CRITICAL")
    errors = sum(1 for i in issues if i.severity == "ERROR")
    warnings = sum(1 for i in issues if i.severity == "WARNING")

    return TopologyValidationReport(
        is_valid=(criticals + errors == 0),
        total_issues=len(issues),
        critical_count=criticals,
        error_count=errors,
        warning_count=warnings,
        issues=issues,
    )


@router.post("/validate-cross-layer", response_model=TopologyValidationReport)
def validate_cross_layer_topology(
    payload: CrossLayerCheckRequest,
    current_user: User = Depends(get_current_user),
) -> TopologyValidationReport:
    """Validate cross-layer constraints: detect buildings crossing parcel boundaries or outside parcels."""
    del current_user
    engine = CadastralTopologyEngine()
    issues = engine.validate_cross_layer(
        parcels=payload.parcels,
        buildings=payload.buildings,
        project_id=payload.project_id,
        dataset_id=payload.dataset_id,
    )
    criticals = sum(1 for i in issues if i.severity == "CRITICAL")
    errors = sum(1 for i in issues if i.severity == "ERROR")
    warnings = sum(1 for i in issues if i.severity == "WARNING")

    return TopologyValidationReport(
        is_valid=(criticals + errors == 0),
        total_issues=len(issues),
        critical_count=criticals,
        error_count=errors,
        warning_count=warnings,
        issues=issues,
    )
