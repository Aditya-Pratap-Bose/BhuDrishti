"""
app/schemas/v2/project.py
-------------------------
Pydantic schemas for V2 survey projects and survey units.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.v2.project import ProjectStatus, SurveyMethod


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=128)
    description: str | None = None
    state: str = Field(..., min_length=2, max_length=64)
    district: str = Field(..., min_length=2, max_length=64)
    ulb: str = Field(..., min_length=2, max_length=128)

    @field_validator("name", "state", "district", "ulb", mode="before")
    @classmethod
    def normalize_required_label(cls, value: str) -> str:
        if not isinstance(value, str):
            raise ValueError("must be a text value")
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("must not be blank")
        return normalized

    @field_validator("description", mode="before")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError("must be a text value")
        normalized = value.strip()
        return normalized or None


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    state: str
    district: str
    ulb: str
    status: ProjectStatus
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime


class ProjectListResponse(BaseModel):
    projects: list[ProjectResponse]
    total: int


class SurveyCreate(BaseModel):
    project_id: uuid.UUID
    survey_unit: str = Field(..., min_length=2, max_length=64)
    survey_method: SurveyMethod = SurveyMethod.DRONE_AERIAL
    survey_date: datetime | None = None
    metadata_info: dict[str, Any] = Field(default_factory=dict)

    @field_validator("survey_unit", mode="before")
    @classmethod
    def normalize_survey_unit(cls, value: str) -> str:
        if not isinstance(value, str):
            raise ValueError("must be a text value")
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("must not be blank")
        return normalized


class SurveyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    survey_unit: str
    survey_method: SurveyMethod
    survey_date: datetime | None
    metadata_info: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class SurveyListResponse(BaseModel):
    surveys: list[SurveyResponse]
    total: int
