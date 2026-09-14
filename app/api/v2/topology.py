"""
app/api/v2/topology.py
----------------------
Authenticated endpoints for comprehensive cadastral topology and cross-layer validation.
Generates structured audit issues (overlaps, gaps, slivers, encroachments).
"""

from __future__ import annotations

import uuid
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from app.api.v1.auth import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.models.v2.validation import ValidationIssue
from app.schemas.v2.validation import ValidationIssueCreate, ValidationIssueListResponse, ValidationIssueResolve, ValidationIssueResponse
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


def _persist_issues(db: Session, issues: list[ValidationIssueCreate]) -> list[ValidationIssue]:
    records = [ValidationIssue(**issue.model_dump()) for issue in issues]
    if records:
        db.add_all(records)
        db.commit()
        for record in records:
            db.refresh(record)
    return records


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


@router.post("/validate-parcels/persist", response_model=ValidationIssueListResponse)
def validate_and_persist_parcel_topology(
    payload: ParcelTopologyCheckRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ValidationIssueListResponse:
    """Validate AI parcels and persist the resulting review issues."""
    del current_user
    engine = CadastralTopologyEngine()
    issues = engine.validate_parcels(
        parcels=payload.parcels,
        project_id=payload.project_id,
        dataset_id=payload.dataset_id,
        min_area_sqm=payload.min_area_sqm,
    )
    records = _persist_issues(db, issues)
    return ValidationIssueListResponse(issues=records, total=len(records), unresolved_count=len(records))


@router.get("/issues", response_model=ValidationIssueListResponse)
def list_topology_issues(
    project_id: uuid.UUID = Query(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ValidationIssueListResponse:
    """List persisted topology issues for a project."""
    del current_user
    records = db.query(ValidationIssue).filter(ValidationIssue.project_id == project_id).order_by(ValidationIssue.created_at.desc()).all()
    unresolved = sum(1 for record in records if record.resolved_at is None)
    return ValidationIssueListResponse(issues=records, total=len(records), unresolved_count=unresolved)


@router.patch("/issues/{issue_id}/resolve", response_model=ValidationIssueResponse)
def resolve_topology_issue(
    issue_id: uuid.UUID,
    payload: ValidationIssueResolve,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ValidationIssueResponse:
    """Record a reviewer resolution note for one persisted topology issue."""
    record = db.query(ValidationIssue).filter(ValidationIssue.id == issue_id).first()
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Validation issue not found.")
    record.resolved_at = datetime.now(timezone.utc)
    record.resolved_by = current_user.id
    record.resolution_note = payload.resolution_note.strip()
    db.commit()
    db.refresh(record)
    return record
