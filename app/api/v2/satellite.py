import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.v1.auth import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.job import JobResponse
from app.schemas.parcel import BBoxRequest
from app.services.v2.job_executor import JobEnqueueError, enqueue_satellite_bbox_job
from app.services.v2.jobs import JobPersistenceError, create_job, transition_job
from app.models.job import JobStatus

logger = logging.getLogger("bhudrishti.api.v2.satellite")
router = APIRouter(prefix="/satellite", tags=["Satellite Processing v2"])


@router.post(
    "/process-bbox",
    response_model=JobResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def process_satellite_bbox(
    payload: BBoxRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> JobResponse:
    """Queue satellite extraction and return a durable polling resource."""
    if payload.source_type == "isro_bhuvan":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "ISRO Bhuvan processing is planned and requires an authorized "
                "government API token."
            ),
        )

    # Keep the request session out of the worker.  It is closed by FastAPI as
    # soon as this response returns.
    try:
        job = create_job(
            db,
            created_by=current_user.id,
            job_type="satellite_bbox",
            request_payload=payload.model_dump(mode="json"),
        )
    except JobPersistenceError as exc:
        logger.exception("Unable to persist v2 bbox job for user %s", current_user.id)
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    try:
        enqueue_satellite_bbox_job(job.id, current_user.id)
    except JobEnqueueError as exc:
        logger.exception("Unable to enqueue v2 bbox job %s", job.id)
        try:
            job = transition_job(
                db,
                job_id=job.id,
                created_by=current_user.id,
                new_status=JobStatus.FAILED,
                error_message=str(exc),
            )
        except Exception:
            logger.exception("Unable to persist enqueue failure for job %s", job.id)
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    bbox = (payload.min_lon, payload.min_lat, payload.max_lon, payload.max_lat)
    logger.info("v2 bbox job %s queued by %s: %s", job.id, current_user.email, bbox)
    return job
