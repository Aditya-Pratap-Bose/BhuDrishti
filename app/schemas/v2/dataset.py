"""
app/schemas/v2/dataset.py
-------------------------
Pydantic schemas for V2 spatial datasets (ORI, DSM, DTM, cadastral layers).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.v2.project import DatasetFormat, DatasetType, ValidationStatus


class DatasetRegisterRequest(BaseModel):
    project_id: uuid.UUID
    survey_id: uuid.UUID | None = None
    name: str = Field(..., min_length=2, max_length=128)
    dataset_type: DatasetType
    format: DatasetFormat
    storage_uri: str = Field(..., min_length=1, max_length=512)
    crs: str | None = None
    bounds: list[float] | None = None
    resolution: list[float] | None = None
    dimensions: list[int] | None = None
    band_count: int | None = None
    gsd: float | None = None
    checksum: str | None = None


class DatasetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    survey_id: uuid.UUID | None
    name: str
    dataset_type: DatasetType
    format: DatasetFormat
    storage_uri: str
    crs: str | None
    bounds: list[float] | None
    resolution: list[float] | None
    dimensions: list[int] | None
    band_count: int | None
    gsd: float | None
    checksum: str | None
    validation_status: ValidationStatus
    validation_report: dict[str, Any] | None
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime


class DatasetListResponse(BaseModel):
    datasets: list[DatasetResponse]
    total: int


class DatasetValidationResult(BaseModel):
    dataset_id: uuid.UUID
    status: ValidationStatus
    is_valid: bool
    report: dict[str, Any]
