"""Authenticated, durable v2 processing job endpoints."""

from __future__ import annotations

import uuid
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.v1.auth import get_current_user
from app.core.database import get_db
from app.models.job import InvalidJobTransitionError
from app.models.user import User
from app.schemas.job import JobCreateRequest, JobListResponse, JobResponse
from app.services.v2.jobs import (
    JobNotFoundError,
    JobPersistenceError,
    cancel_job,
    create_job,
    get_job,
    list_jobs,
)
from app.services.v2.job_executor import (
    JobEnqueueError,
    enqueue_satellite_bbox_job,
)

logger = logging.getLogger("bhudrishti.api.v2.jobs")

router = APIRouter(prefix="/jobs", tags=["v2 Processing Jobs"])


@router.post("", response_model=JobResponse, status_code=status.HTTP_202_ACCEPTED)
def create_processing_job(
    payload: JobCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> JobResponse:
    """Persist and enqueue a supported v2 job."""
    if payload.job_type != "satellite_bbox":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="This job type is planned and is not executable yet.",
        )
    try:
        # Validate the worker payload before writing a job that could never run.
        from app.schemas.parcel import BBoxRequest

        BBoxRequest.model_validate(payload.payload)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="satellite_bbox payload must be a valid bounding-box request.",
        ) from exc
    try:
        job = create_job(
            db,
            created_by=current_user.id,
            job_type=payload.job_type,
            request_payload=payload.payload,
        )
        try:
            enqueue_satellite_bbox_job(job.id, current_user.id)
        except JobEnqueueError as exc:
            # Persistence succeeded, so expose a durable failure rather than
            # claiming the request disappeared.
            from app.models.job import JobStatus
            from app.services.v2.jobs import transition_job

            transition_job(
                db,
                job_id=job.id,
                created_by=current_user.id,
                new_status=JobStatus.FAILED,
                error_message=str(exc),
            )
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return job
    except JobPersistenceError as exc:
        logger.exception("Unable to persist v2 job for user %s", current_user.id)
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/{job_id}", response_model=JobResponse)
def get_processing_job(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> JobResponse:
    """Return a job only to the user who created it."""
    try:
        return get_job(db, job_id=job_id, created_by=current_user.id)
    except JobNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except JobPersistenceError as exc:
        logger.exception("Unable to read v2 job %s", job_id)
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("", response_model=JobListResponse)
def list_processing_jobs(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> JobListResponse:
    """List jobs owned by the caller for polling and audit screens."""
    try:
        jobs, total = list_jobs(
            db, created_by=current_user.id, limit=limit, offset=offset
        )
        return JobListResponse(jobs=jobs, total=total)
    except JobPersistenceError as exc:
        logger.exception("Unable to list v2 jobs for user %s", current_user.id)
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/{job_id}/cancel", response_model=JobResponse)
def cancel_processing_job(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> JobResponse:
    """Cancel a queued job; running jobs are owned by the worker."""
    try:
        return cancel_job(db, job_id=job_id, created_by=current_user.id)
    except JobNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InvalidJobTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except JobPersistenceError as exc:
        logger.exception("Unable to update v2 job %s", job_id)
        raise HTTPException(status_code=503, detail=str(exc)) from exc
