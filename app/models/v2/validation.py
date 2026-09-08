"""
app/models/v2/validation.py
---------------------------
Relational data model for cadastral topology and quality validation issues.
Generates structured audit issues without destructively mutating geometries.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, Enum as SQLEnum, ForeignKey, Index, JSON, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class IssueSeverity(str, enum.Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class IssueType(str, enum.Enum):
    PARCEL_OVERLAP = "PARCEL_OVERLAP"
    PARCEL_GAP = "PARCEL_GAP"
    INVALID_GEOMETRY = "INVALID_GEOMETRY"
    SLIVER = "SLIVER"
    DUPLICATE = "DUPLICATE"
    BOUNDARY_MISMATCH = "BOUNDARY_MISMATCH"
    BUILDING_OUTSIDE_PARCEL = "BUILDING_OUTSIDE_PARCEL"
    BUILDING_CROSSING_BOUNDARY = "BUILDING_CROSSING_BOUNDARY"
    ROAD_CONFLICT = "ROAD_CONFLICT"
    DISCONNECTED_ACCESS = "DISCONNECTED_ACCESS"
    LOW_AI_CONFIDENCE = "LOW_AI_CONFIDENCE"
    CRS_MISMATCH = "CRS_MISMATCH"


class ValidationIssue(Base):
    """Represents a spatial integrity or cadastral policy violation."""

    __tablename__ = "v2_validation_issues"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("v2_projects.id"), nullable=False, index=True
    )
    dataset_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("v2_datasets.id"), nullable=True, index=True
    )
    feature_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    issue_type: Mapped[IssueType] = mapped_column(
        SQLEnum(
            IssueType,
            name="v2_issue_type_enum",
            values_callable=lambda issues: [i.value for i in issues],
        ),
        nullable=False,
        index=True,
    )
    severity: Mapped[IssueSeverity] = mapped_column(
        SQLEnum(
            IssueSeverity,
            name="v2_issue_severity_enum",
            values_callable=lambda severities: [s.value for s in severities],
        ),
        nullable=False,
        default=IssueSeverity.WARNING,
        index=True,
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    geometry: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    detected_by: Mapped[str] = mapped_column(String(128), default="TopologyEngine/v2.0", nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    resolution_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utc_now, nullable=False
    )

    __table_args__ = (
        Index("idx_v2_issues_project_severity", "project_id", "severity"),
    )
