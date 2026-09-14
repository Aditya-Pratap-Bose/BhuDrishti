"""
app/api/v2/projects.py
----------------------
Authenticated endpoints for managing government survey projects and survey units.
"""

from __future__ import annotations

import uuid
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.v1.auth import get_current_user
from app.core.database import get_db
from app.core.exceptions import DatasetValidationError
from app.models.user import User
from app.schemas.v2.project import (
    ProjectCreate,
    ProjectListResponse,
    ProjectResponse,
    SurveyCreate,
    SurveyListResponse,
    SurveyResponse,
)
from app.schemas.v2.administrative import SurveyAoiUpdate
from app.services.v2.ingestion.dataset_registry import (
    create_project,
    create_survey,
    get_project,
    list_projects,
    list_surveys,
    update_survey_aoi,
)

logger = logging.getLogger("bhudrishti.api.v2.projects")

router = APIRouter(prefix="/projects", tags=["v2 Survey Projects"])


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_survey_project(
    payload: ProjectCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProjectResponse:
    """Create a new administrative survey project (e.g. ULB or Tehsil land survey)."""
    return create_project(db, payload, created_by=current_user.id)


@router.get("", response_model=ProjectListResponse)
def list_survey_projects(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProjectListResponse:
    """List administrative survey projects."""
    del current_user
    projects, total = list_projects(db, limit=limit, offset=offset)
    return ProjectListResponse(projects=projects, total=total)


@router.get("/{project_id}", response_model=ProjectResponse)
def get_survey_project(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProjectResponse:
    """Retrieve details of a specific survey project."""
    del current_user
    try:
        return get_project(db, project_id)
    except DatasetValidationError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/{project_id}/surveys", response_model=SurveyResponse, status_code=status.HTTP_201_CREATED)
def create_project_survey_unit(
    project_id: uuid.UUID,
    payload: SurveyCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SurveyResponse:
    """Create a new survey unit or campaign within a project."""
    del current_user
    if payload.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Route project_id does not match payload.")
    try:
        return create_survey(db, payload)
    except DatasetValidationError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/{project_id}/surveys", response_model=SurveyListResponse)
def list_project_surveys(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SurveyListResponse:
    """List all survey units associated with a project."""
    del current_user
    try:
        get_project(db, project_id)
        surveys = list_surveys(db, project_id)
        return SurveyListResponse(surveys=surveys, total=len(surveys))
    except DatasetValidationError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.patch("/{project_id}/surveys/{survey_id}/aoi", response_model=SurveyResponse)
def update_project_survey_aoi(
    project_id: uuid.UUID,
    survey_id: uuid.UUID,
    payload: SurveyAoiUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SurveyResponse:
    """Persist a WGS84 AOI bbox on an existing survey unit."""
    del current_user
    try:
        return update_survey_aoi(db, project_id, survey_id, payload.bbox, payload.source, payload.geometry)
    except DatasetValidationError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
