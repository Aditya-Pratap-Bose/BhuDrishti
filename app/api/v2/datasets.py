"""
app/api/v2/datasets.py
----------------------
Authenticated endpoints for spatial dataset asset registration and validation.
Supports ORI, DSM, DTM, DEM, existing parcels, GNSS, and CORS datasets.
"""

from __future__ import annotations

import uuid
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.v1.auth import get_current_user
from app.core.database import get_db
from app.core.exceptions import DatasetValidationError
from app.models.user import User
from app.models.v2.project import DatasetType
from app.schemas.v2.dataset import (
    DatasetListResponse,
    DatasetRegisterRequest,
    DatasetResponse,
    DatasetValidationResult,
)
from app.services.v2.ingestion.dataset_registry import (
    get_dataset,
    list_datasets,
    register_dataset,
    validate_dataset,
)

logger = logging.getLogger("bhudrishti.api.v2.datasets")

router = APIRouter(prefix="/datasets", tags=["v2 Datasets & Assets"])


@router.post("", response_model=DatasetResponse, status_code=status.HTTP_201_CREATED)
def register_spatial_dataset(
    payload: DatasetRegisterRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DatasetResponse:
    """Register a new spatial asset (ORI, DSM, DTM, cadastral overlay, GNSS/CORS)."""
    try:
        return register_dataset(db, payload, created_by=current_user.id)
    except DatasetValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.get("", response_model=DatasetListResponse)
def list_spatial_datasets(
    project_id: uuid.UUID = Query(..., description="Project ID to query datasets for"),
    dataset_type: DatasetType | None = Query(None, description="Optional dataset type filter"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DatasetListResponse:
    """List registered spatial datasets for a project."""
    del current_user
    datasets, total = list_datasets(
        db, project_id=project_id, dataset_type=dataset_type, limit=limit, offset=offset
    )
    return DatasetListResponse(datasets=datasets, total=total)


@router.get("/{dataset_id}", response_model=DatasetResponse)
def get_spatial_dataset(
    dataset_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DatasetResponse:
    """Retrieve metadata and validation status of a dataset."""
    del current_user
    try:
        return get_dataset(db, dataset_id)
    except DatasetValidationError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/{dataset_id}/validate", response_model=DatasetValidationResult)
def validate_spatial_dataset(
    dataset_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DatasetValidationResult:
    """Trigger validation on a dataset and return structured report."""
    del current_user
    try:
        return validate_dataset(db, dataset_id)
    except DatasetValidationError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
