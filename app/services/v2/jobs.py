"""Database-backed v2 processing job operations."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.job import (
    InvalidJobTransitionError,
    JobStatus,
    ProcessingJob,
)


class JobPersistenceError(RuntimeError):
    """Raised when a job cannot be read or written to the configured database."""


class JobNotFoundError(LookupError):
    """Raised when a job is not visible to the requesting user."""


def create_job(
    db: Session,
    *,
    created_by: uuid.UUID,
    job_type: str,
    request_payload: dict[str, Any],
) -> ProcessingJob:
    job = ProcessingJob(
        created_by=created_by,
        job_type=job_type,
        request_payload=request_payload,
        status=JobStatus.QUEUED,
    )
    db.add(job)
    try:
        db.commit()
        db.refresh(job)
    except SQLAlchemyError as exc:
        db.rollback()
        raise JobPersistenceError(
            "The processing job could not be persisted to the database."
        ) from exc
    return job


def get_job(
    db: Session, *, job_id: uuid.UUID, created_by: uuid.UUID
) -> ProcessingJob:
    try:
        job = (
            db.query(ProcessingJob)
            .filter(
                ProcessingJob.id == job_id,
                ProcessingJob.created_by == created_by,
            )
            .first()
        )
    except SQLAlchemyError as exc:
        raise JobPersistenceError(
            "The processing job could not be read from the database."
        ) from exc
    if job is None:
        raise JobNotFoundError("Processing job not found.")
    return job


def list_jobs(
    db: Session,
    *,
    created_by: uuid.UUID,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[ProcessingJob], int]:
    """Return only the caller's jobs, newest first, with bounded pagination."""
    limit = max(1, min(limit, 100))
    offset = max(0, offset)
    try:
        query = db.query(ProcessingJob).filter(ProcessingJob.created_by == created_by)
        total = query.with_entities(func.count(ProcessingJob.id)).scalar() or 0
        jobs = (
            query.order_by(ProcessingJob.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
    except SQLAlchemyError as exc:
        raise JobPersistenceError(
            "The processing jobs could not be read from the database."
        ) from exc
    return jobs, total


def transition_job(
    db: Session,
    *,
    job_id: uuid.UUID,
    created_by: uuid.UUID,
    new_status: JobStatus,
    result_payload: dict[str, Any] | None = None,
    error_message: str | None = None,
) -> ProcessingJob:
    try:
        # Lock the row so two workers cannot both advance the same job based
        # on a stale status. PostgreSQL enforces this; SQLite ignores it.
        job = (
            db.query(ProcessingJob)
            .filter(
                ProcessingJob.id == job_id,
                ProcessingJob.created_by == created_by,
            )
            .with_for_update()
            .first()
        )
        if job is None:
            raise JobNotFoundError("Processing job not found.")
        job.transition_to(
            new_status,
            result_payload=result_payload,
            error_message=error_message,
        )
        db.commit()
        db.refresh(job)
    except JobNotFoundError:
        db.rollback()
        raise
    except InvalidJobTransitionError:
        db.rollback()
        raise
    except SQLAlchemyError as exc:
        db.rollback()
        raise JobPersistenceError(
            "The processing job status could not be persisted to the database."
        ) from exc
    return job


def cancel_job(
    db: Session, *, job_id: uuid.UUID, created_by: uuid.UUID
) -> ProcessingJob:
    """Cancel a queued job before a worker claims it."""
    try:
        job = (
            db.query(ProcessingJob)
            .filter(
                ProcessingJob.id == job_id,
                ProcessingJob.created_by == created_by,
            )
            .with_for_update()
            .first()
        )
        if job is None:
            raise JobNotFoundError("Processing job not found.")
        if job.status is not JobStatus.QUEUED:
            raise InvalidJobTransitionError(
                "Only queued processing jobs can be cancelled."
            )
        job.transition_to(JobStatus.CANCELLED)
        db.commit()
        db.refresh(job)
    except (JobNotFoundError, InvalidJobTransitionError):
        db.rollback()
        raise
    except SQLAlchemyError as exc:
        db.rollback()
        raise JobPersistenceError(
            "The processing job could not be cancelled."
        ) from exc
    return job
