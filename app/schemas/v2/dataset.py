"""
app/schemas/v2/dataset.py
-------------------------
Pydantic schemas for V2 spatial datasets (ORI, DSM, DTM, cadastral layers).
"""

from __future__ import annotations

import uuid
from datetime import datetime
import math
import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

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

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        if not isinstance(value, str):
            raise ValueError("must be a text value")
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("must not be blank")
        return normalized

    @field_validator("storage_uri", mode="before")
    @classmethod
    def validate_storage_uri(cls, value: str) -> str:
        if not isinstance(value, str):
            raise ValueError("must be a text value")
        normalized = value.strip()
        if not normalized:
            raise ValueError("must not be blank")
        return normalized

    @field_validator("bounds")
    @classmethod
    def validate_bounds(cls, value: list[float] | None) -> list[float] | None:
        if value is None:
            return None
        if len(value) != 4 or not all(math.isfinite(item) for item in value):
            raise ValueError("bounds must contain four finite values")
        min_x, min_y, max_x, max_y = value
        if min_x >= max_x or min_y >= max_y:
            raise ValueError("bounds must be ordered as min_x, min_y, max_x, max_y")
        return value

    @field_validator("resolution")
    @classmethod
    def validate_resolution(cls, value: list[float] | None) -> list[float] | None:
        if value is None:
            return None
        if len(value) != 2 or not all(math.isfinite(item) and item > 0 for item in value):
            raise ValueError("resolution must contain two positive finite values")
        return value

    @field_validator("dimensions")
    @classmethod
    def validate_dimensions(cls, value: list[int] | None) -> list[int] | None:
        if value is None:
            return None
        if len(value) != 2 or not all(item > 0 for item in value):
            raise ValueError("dimensions must contain two positive values")
        return value

    @field_validator("band_count")
    @classmethod
    def validate_band_count(cls, value: int | None) -> int | None:
        if value is not None and value < 1:
            raise ValueError("band_count must be positive")
        return value

    @field_validator("gsd")
    @classmethod
    def validate_gsd(cls, value: float | None) -> float | None:
        if value is not None and (not math.isfinite(value) or value <= 0):
            raise ValueError("gsd must be a positive finite value")
        return value

    @field_validator("checksum")
    @classmethod
    def validate_checksum(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        if not re.fullmatch(r"[0-9a-f]{64}", normalized):
            raise ValueError("checksum must be a 64-character SHA-256 hex digest")
        return normalized


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
