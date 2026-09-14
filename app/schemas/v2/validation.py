"""
app/schemas/v2/validation.py
----------------------------
Pydantic schemas for cadastral validation issues.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.v2.validation import IssueSeverity, IssueType


class ValidationIssueCreate(BaseModel):
    project_id: uuid.UUID
    dataset_id: uuid.UUID | None = None
    feature_id: str | None = None
    issue_type: IssueType
    severity: IssueSeverity = IssueSeverity.WARNING
    description: str
    geometry: dict[str, Any] | None = None
    detected_by: str = "CadastralTopologyEngine/v2.0"


class ValidationIssueResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    dataset_id: uuid.UUID | None
    feature_id: str | None
    issue_type: IssueType
    severity: IssueSeverity
    description: str
    geometry: dict[str, Any] | None
    detected_by: str
    resolved_at: datetime | None
    resolved_by: uuid.UUID | None
    resolution_note: str | None
    created_at: datetime


class ValidationIssueListResponse(BaseModel):
    issues: list[ValidationIssueResponse]
    total: int
    unresolved_count: int


class ValidationIssueResolve(BaseModel):
    resolution_note: str = Field(..., min_length=2, max_length=1000)
