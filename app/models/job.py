"""Durable v2 processing job records and lifecycle rules."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, Enum as SQLEnum, ForeignKey, Index, JSON, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class JobStatus(str, enum.Enum):
    """Statuses understood by the v2 worker contract."""

    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class InvalidJobTransitionError(ValueError):
    """Raised when a job lifecycle transition is not allowed."""


_ALLOWED_TRANSITIONS: dict[JobStatus, frozenset[JobStatus]] = {
    JobStatus.QUEUED: frozenset(
        {JobStatus.RUNNING, JobStatus.FAILED, JobStatus.CANCELLED}
    ),
    JobStatus.RUNNING: frozenset(
        {JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.CANCELLED}
    ),
    JobStatus.SUCCEEDED: frozenset(),
    JobStatus.FAILED: frozenset(),
    JobStatus.CANCELLED: frozenset(),
}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ProcessingJob(Base):
    """A v2 processing request whose state survives process restarts."""

    __tablename__ = "processing_jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    job_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[JobStatus] = mapped_column(
        SQLEnum(
            JobStatus,
            name="processing_job_status_enum",
            values_callable=lambda statuses: [status.value for status in statuses],
        ),
        nullable=False,
        default=JobStatus.QUEUED,
        index=True,
    )
    request_payload: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    result_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utc_now, onupdate=_utc_now, nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        Index("idx_processing_jobs_owner_created", "created_by", "created_at"),
        Index("idx_processing_jobs_status_created", "status", "created_at"),
    )

    def transition_to(
        self,
        new_status: JobStatus,
        *,
        result_payload: dict[str, Any] | None = None,
        error_message: str | None = None,
    ) -> None:
        """Apply one validated lifecycle transition to this job."""
        try:
            target = JobStatus(new_status)
        except (TypeError, ValueError) as exc:
            raise InvalidJobTransitionError(
                f"Unsupported processing job status: {new_status!r}."
            ) from exc

        if target not in _ALLOWED_TRANSITIONS[self.status]:
            raise InvalidJobTransitionError(
                f"Cannot transition job from '{self.status.value}' to '{target.value}'."
            )
        if target is JobStatus.FAILED and not error_message:
            raise InvalidJobTransitionError(
                "A failed processing job must include an error message."
            )
        if target is not JobStatus.FAILED and error_message is not None:
            raise InvalidJobTransitionError(
                "An error message is only valid when marking a job as failed."
            )
        if target is JobStatus.SUCCEEDED and result_payload is None:
            raise InvalidJobTransitionError(
                "A succeeded processing job must include a result payload."
            )
        if target is not JobStatus.SUCCEEDED and result_payload is not None:
            raise InvalidJobTransitionError(
                "A result payload is only valid when marking a job as succeeded."
            )

        now = _utc_now()
        self.status = target
        self.updated_at = now
        if target is JobStatus.RUNNING:
            self.started_at = now
        elif target in {
            JobStatus.SUCCEEDED,
            JobStatus.FAILED,
            JobStatus.CANCELLED,
        }:
            self.completed_at = now

        if target is JobStatus.SUCCEEDED:
            self.result_payload = result_payload
            self.error_message = None
        elif target is JobStatus.FAILED:
            self.error_message = error_message


# Keep the shorter name available for callers that refer to the table as jobs.
Job = ProcessingJob
