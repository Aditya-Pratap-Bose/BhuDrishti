"""
app/api/v2/review.py
--------------------
Authenticated endpoints for managing the project review workflow.
Supports reading current review state, transitioning state, and listing
the review decision audit trail.
"""

from __future__ import annotations

import uuid
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.v1.auth import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.models.v2.review import ReviewDecision, ReviewState, REVIEW_TRANSITIONS

logger = logging.getLogger("bhudrishti.api.v2.review")

router = APIRouter(prefix="/review", tags=["v2 Review Workflow"])


class ReviewStateResponse(BaseModel):
    project_id: str
    current_state: str
    available_transitions: list[str]
    decision_count: int


class ReviewTransitionRequest(BaseModel):
    to_state: str = Field(..., description="Target review state")
    note: str | None = Field(default=None, max_length=500)


class ReviewDecisionResponse(BaseModel):
    id: str
    project_id: str
    from_state: str
    to_state: str
    reviewer_id: str
    note: str | None
    created_at: str


@router.get("/state")
def get_review_state(
    project_id: uuid.UUID = Query(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReviewStateResponse:
    """Get the current review state for a project."""
    del current_user
    latest = (
        db.query(ReviewDecision)
        .filter(ReviewDecision.project_id == project_id)
        .order_by(ReviewDecision.created_at.desc())
        .first()
    )
    current = ReviewState(latest.to_state) if latest else ReviewState.AI_GENERATED
    transitions = REVIEW_TRANSITIONS.get(current, [])
    count = db.query(ReviewDecision).filter(ReviewDecision.project_id == project_id).count()
    return ReviewStateResponse(
        project_id=str(project_id),
        current_state=current.value,
        available_transitions=[t.value for t in transitions],
        decision_count=count,
    )


@router.post("/transition")
def transition_review_state(
    project_id: uuid.UUID = Query(...),
    payload: ReviewTransitionRequest = ...,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReviewDecisionResponse:
    """Transition the review state for a project. Only valid transitions are allowed."""
    try:
        target = ReviewState(payload.to_state)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid review state: {payload.to_state}. Valid states: {[s.value for s in ReviewState]}",
        )

    latest = (
        db.query(ReviewDecision)
        .filter(ReviewDecision.project_id == project_id)
        .order_by(ReviewDecision.created_at.desc())
        .first()
    )
    current = ReviewState(latest.to_state) if latest else ReviewState.AI_GENERATED
    allowed = REVIEW_TRANSITIONS.get(current, [])

    if target not in allowed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot transition from {current.value} to {target.value}. "
                   f"Allowed: {[t.value for t in allowed]}",
        )

    decision = ReviewDecision(
        project_id=project_id,
        from_state=current,
        to_state=target,
        reviewer_id=current_user.id,
        note=payload.note.strip() if payload.note else None,
    )
    db.add(decision)
    db.commit()
    db.refresh(decision)

    logger.info(
        "Review transition %s -> %s for project %s by user %s",
        current.value, target.value, project_id, current_user.id,
    )

    return ReviewDecisionResponse(
        id=str(decision.id),
        project_id=str(decision.project_id),
        from_state=decision.from_state.value if isinstance(decision.from_state, ReviewState) else str(decision.from_state),
        to_state=decision.to_state.value if isinstance(decision.to_state, ReviewState) else str(decision.to_state),
        reviewer_id=str(decision.reviewer_id),
        note=decision.note,
        created_at=decision.created_at.isoformat(),
    )


@router.get("/decisions")
def list_review_decisions(
    project_id: uuid.UUID = Query(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ReviewDecisionResponse]:
    """List the review decision audit trail for a project."""
    del current_user
    records = (
        db.query(ReviewDecision)
        .filter(ReviewDecision.project_id == project_id)
        .order_by(ReviewDecision.created_at.asc())
        .all()
    )
    return [
        ReviewDecisionResponse(
            id=str(r.id),
            project_id=str(r.project_id),
            from_state=r.from_state.value if isinstance(r.from_state, ReviewState) else str(r.from_state),
            to_state=r.to_state.value if isinstance(r.to_state, ReviewState) else str(r.to_state),
            reviewer_id=str(r.reviewer_id),
            note=r.note,
            created_at=r.created_at.isoformat(),
        )
        for r in records
    ]
