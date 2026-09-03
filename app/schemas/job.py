"""Pydantic contracts for the persistent v2 processing job API."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.job import JobStatus


class JobCreateRequest(BaseModel):
    """Create a queued job; execution is intentionally owned by a worker."""

    job_type: str = Field(
        min_length=2,
        max_length=64,
        pattern=r"^[a-z][a-z0-9_.-]*$",
        description="Stable worker operation name, for example satellite_bbox.",
    )
    payload: dict[str, Any] = Field(default_factory=dict)


class JobStatusUpdateRequest(BaseModel):
    """Worker lifecycle update with fields appropriate to the target status."""

    status: JobStatus
    result_payload: dict[str, Any] | None = None
    error_message: str | None = Field(default=None, min_length=1, max_length=2000)

    @model_validator(mode="after")
    def validate_status_payload(self) -> "JobStatusUpdateRequest":
        if self.status is JobStatus.SUCCEEDED and self.result_payload is None:
            raise ValueError("result_payload is required when status is succeeded.")
        if self.status is JobStatus.FAILED and self.error_message is None:
            raise ValueError("error_message is required when status is failed.")
        if self.status is not JobStatus.SUCCEEDED and self.result_payload is not None:
            raise ValueError(
                "result_payload is only accepted when status is succeeded."
            )
        if self.status is not JobStatus.FAILED and self.error_message is not None:
            raise ValueError("error_message is only accepted when status is failed.")
        return self


class JobResponse(BaseModel):
    type: str = "ProcessingJob"
    id: uuid.UUID
    created_by: uuid.UUID
    job_type: str
    status: JobStatus
    request_payload: dict[str, Any]
    result_payload: dict[str, Any] | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None
    completed_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class JobListResponse(BaseModel):
    """Stable envelope used by clients polling the owned job collection."""

    type: str = "ProcessingJobList"
    jobs: list[JobResponse]
    total: int
