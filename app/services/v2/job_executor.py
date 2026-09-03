"""Bounded background execution for durable v2 processing jobs.

The executor owns a fresh SQLAlchemy session for every job.  API request
sessions therefore never leak into background work, and every outcome is
recorded in the durable lifecycle before the worker exits.  A deployment that
needs multi-process throughput can replace this module with a queue adapter
without changing the v2 API contract.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import uuid
from concurrent.futures import Executor, ThreadPoolExecutor

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.job import InvalidJobTransitionError, JobStatus, ProcessingJob
from app.schemas.parcel import BBoxRequest, ParcelGeoJSONResponse
from app.services.ai.sam_engine import (
    ColabProcessingError,
    ColabTimeoutError,
    ColabUnreachableError,
    SamEngineError,
    process_bbox,
)
from app.services.v2.jobs import (
    JobNotFoundError,
    JobPersistenceError,
    get_job,
    transition_job,
)

logger = logging.getLogger("bhudrishti.v2.job_executor")

_executor: ThreadPoolExecutor | None = None
_executor_lock = threading.Lock()


class JobEnqueueError(RuntimeError):
    """Raised when a persisted job cannot be handed to the worker."""


def _get_executor() -> Executor:
    global _executor
    with _executor_lock:
        if _executor is None:
            workers = max(1, int(settings.V2_JOB_WORKERS))
            _executor = ThreadPoolExecutor(
                max_workers=workers,
                thread_name_prefix="bhudrishti-v2-job",
            )
        return _executor


def _processing_error(exc: Exception) -> str:
    """Map engine failures to actionable but non-sensitive API text."""
    if isinstance(exc, (ColabUnreachableError, ColabTimeoutError, ColabProcessingError)):
        return str(exc)
    if isinstance(exc, SamEngineError):
        return str(exc)
    if isinstance(exc, ValueError):
        return f"Invalid processing result: {exc}"
    return "Satellite processing failed unexpectedly. Check the server logs."


def _run_satellite_bbox_job(job_id: uuid.UUID, created_by: uuid.UUID) -> None:
    db = SessionLocal()
    try:
        try:
            transition_job(
                db,
                job_id=job_id,
                created_by=created_by,
                new_status=JobStatus.RUNNING,
            )
        except (JobNotFoundError, InvalidJobTransitionError):
            # A caller may have cancelled the queued job while it was waiting.
            logger.info("Skipping job %s because it is no longer runnable", job_id)
            return
        except JobPersistenceError:
            logger.exception("Could not claim v2 job %s", job_id)
            return

        job = get_job(db, job_id=job_id, created_by=created_by)
        if job.job_type != "satellite_bbox":
            raise ValueError(f"Unsupported v2 job type '{job.job_type}'.")

        request = BBoxRequest.model_validate(job.request_payload)
        if request.source_type == "isro_bhuvan":
            raise ValueError(
                "ISRO Bhuvan processing is planned and requires an authorized government API token."
            )
        bbox = (request.min_lon, request.min_lat, request.max_lon, request.max_lat)
        raw_result = asyncio.run(process_bbox(bbox, request.source_type))
        result = ParcelGeoJSONResponse.model_validate(raw_result)
        transition_job(
            db,
            job_id=job_id,
            created_by=created_by,
            new_status=JobStatus.SUCCEEDED,
            result_payload=result.model_dump(mode="json"),
        )
        logger.info("v2 satellite bbox job %s succeeded", job_id)
    except Exception as exc:
        logger.exception("v2 satellite bbox job %s failed", job_id)
        try:
            transition_job(
                db,
                job_id=job_id,
                created_by=created_by,
                new_status=JobStatus.FAILED,
                error_message=_processing_error(exc)[:2000],
            )
        except Exception:
            logger.exception("Could not persist failure for v2 job %s", job_id)
    finally:
        db.close()


def enqueue_satellite_bbox_job(job_id: uuid.UUID, created_by: uuid.UUID) -> None:
    """Submit a persisted satellite job without doing work in the HTTP request."""
    try:
        _get_executor().submit(_run_satellite_bbox_job, job_id, created_by)
    except (RuntimeError, ValueError) as exc:
        raise JobEnqueueError("The processing worker is not available.") from exc


def recover_queued_jobs() -> int:
    """Re-submit queued jobs after an API process restart."""
    db = SessionLocal()
    try:
        jobs = (
            db.query(ProcessingJob)
            .filter_by(status=JobStatus.QUEUED)
            .order_by(ProcessingJob.created_at)
            .limit(max(0, int(settings.V2_JOB_RECOVERY_LIMIT)))
            .all()
        )
        recovered = 0
        for job in jobs:
            try:
                enqueue_satellite_bbox_job(job.id, job.created_by)
                recovered += 1
            except JobEnqueueError:
                logger.exception("Could not recover queued v2 job %s", job.id)
        return recovered
    except Exception:
        logger.exception("Could not inspect queued v2 jobs for recovery")
        return 0
    finally:
        db.close()


def shutdown_executor() -> None:
    """Stop accepting work during graceful application shutdown."""
    global _executor
    with _executor_lock:
        executor, _executor = _executor, None
    if executor is not None:
        executor.shutdown(wait=True, cancel_futures=False)
