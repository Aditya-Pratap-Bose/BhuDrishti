"""
app/models/v2/review.py
-----------------------
Relational data model for project-level review workflow states.
Tracks the lifecycle of cadastral candidate review:
AI_GENERATED -> AUTO_VALIDATED -> UNDER_REVIEW -> FIELD_VERIFIED -> APPROVED.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, Enum as SQLEnum, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ReviewState(str, enum.Enum):
    AI_GENERATED = "AI_GENERATED"
    AUTO_VALIDATED = "AUTO_VALIDATED"
    UNDER_REVIEW = "UNDER_REVIEW"
    FIELD_VERIFIED = "FIELD_VERIFIED"
    APPROVED = "APPROVED"


# Valid forward transitions
REVIEW_TRANSITIONS: dict[ReviewState, list[ReviewState]] = {
    ReviewState.AI_GENERATED: [ReviewState.AUTO_VALIDATED],
    ReviewState.AUTO_VALIDATED: [ReviewState.UNDER_REVIEW],
    ReviewState.UNDER_REVIEW: [ReviewState.FIELD_VERIFIED, ReviewState.AI_GENERATED],
    ReviewState.FIELD_VERIFIED: [ReviewState.APPROVED, ReviewState.UNDER_REVIEW],
    ReviewState.APPROVED: [],
}


class ReviewDecision(Base):
    """Records each state transition in the project review workflow."""

    __tablename__ = "v2_review_decisions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("v2_projects.id"), nullable=False, index=True
    )
    from_state: Mapped[ReviewState] = mapped_column(
        SQLEnum(
            ReviewState,
            name="v2_review_state_enum",
            values_callable=lambda states: [s.value for s in states],
            create_constraint=False,
        ),
        nullable=False,
    )
    to_state: Mapped[ReviewState] = mapped_column(
        SQLEnum(
            ReviewState,
            name="v2_review_state_enum",
            values_callable=lambda states: [s.value for s in states],
            create_constraint=False,
        ),
        nullable=False,
    )
    reviewer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utc_now, nullable=False
    )

    __table_args__ = (
        Index("idx_v2_review_project", "project_id"),
    )
