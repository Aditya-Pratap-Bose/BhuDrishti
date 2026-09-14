"""
app/services/v2/ingestion/dataset_registry.py
---------------------------------------------
Service layer for managing projects, surveys, and spatial dataset assets.
Enforces validation rules, metadata extraction, and lifecycle tracking.
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.core.exceptions import DatasetValidationError, RasterValidationError
from app.models.v2.project import (
    Dataset,
    DatasetFormat,
    DatasetType,
    Project,
    ProjectStatus,
    Survey,
    ValidationStatus,
)
from app.schemas.v2.dataset import DatasetRegisterRequest, DatasetValidationResult
from app.schemas.v2.project import ProjectCreate, SurveyCreate
from app.services.v2.raster import inspect_raster

logger = logging.getLogger("bhudrishti.v2.dataset_registry")


def _calculate_checksum(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------
def create_project(
    db: Session, payload: ProjectCreate, created_by: uuid.UUID
) -> Project:
    project = Project(
        name=payload.name,
        description=payload.description,
        state=payload.state,
        district=payload.district,
        ulb=payload.ulb,
        status=ProjectStatus.ACTIVE,
        created_by=created_by,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    logger.info("Created v2 project %s (%s) for user %s", project.id, project.name, created_by)
    return project


def get_project(db: Session, project_id: uuid.UUID) -> Project:
    project = db.query(Project).filter_by(id=project_id).first()
    if not project:
        raise DatasetValidationError(f"Project '{project_id}' not found.")
    return project


def list_projects(
    db: Session, limit: int = 50, offset: int = 0
) -> tuple[list[Project], int]:
    query = db.query(Project)
    total = query.count()
    projects = query.order_by(Project.created_at.desc()).offset(offset).limit(limit).all()
    return projects, total


# ---------------------------------------------------------------------------
# Surveys
# ---------------------------------------------------------------------------
def create_survey(db: Session, payload: SurveyCreate) -> Survey:
    # Verify project exists
    get_project(db, payload.project_id)
    survey = Survey(
        project_id=payload.project_id,
        survey_unit=payload.survey_unit,
        survey_method=payload.survey_method,
        survey_date=payload.survey_date,
        metadata_info=payload.metadata_info,
    )
    db.add(survey)
    db.commit()
    db.refresh(survey)
    logger.info("Created v2 survey unit %s under project %s", survey.survey_unit, payload.project_id)
    return survey


def list_surveys(db: Session, project_id: uuid.UUID) -> list[Survey]:
    return (
        db.query(Survey)
        .filter_by(project_id=project_id)
        .order_by(Survey.created_at.asc())
        .all()
    )


def update_survey_aoi(
    db: Session,
    project_id: uuid.UUID,
    survey_id: uuid.UUID,
    bbox: list[float],
    source: str,
    geometry: dict | None = None,
) -> Survey:
    survey = (
        db.query(Survey)
        .filter(Survey.id == survey_id, Survey.project_id == project_id)
        .first()
    )
    if not survey:
        raise DatasetValidationError(f"Survey '{survey_id}' not found in project '{project_id}'.")
    metadata = dict(survey.metadata_info or {})
    metadata["aoi"] = {
        "type": "polygon" if geometry else "bbox",
        "bbox": bbox,
        "geometry": geometry,
        "source": source,
        "crs": "EPSG:4326",
    }
    survey.metadata_info = metadata
    db.commit()
    db.refresh(survey)
    logger.info("Updated AOI for survey %s under project %s", survey_id, project_id)
    return survey


# ---------------------------------------------------------------------------
# Datasets
# ---------------------------------------------------------------------------
def register_dataset(
    db: Session, payload: DatasetRegisterRequest, created_by: uuid.UUID
) -> Dataset:
    # Verify project exists
    get_project(db, payload.project_id)
    if payload.survey_id:
        survey = db.query(Survey).filter_by(id=payload.survey_id, project_id=payload.project_id).first()
        if not survey:
            raise DatasetValidationError("Referenced survey does not belong to this project.")

    storage_path = Path(payload.storage_uri)
    metadata: dict[str, Any] = {}
    checksum = payload.checksum
    crs = payload.crs
    bounds = payload.bounds
    resolution = payload.resolution
    dimensions = payload.dimensions
    band_count = payload.band_count
    gsd = payload.gsd
    validation_status = ValidationStatus.PENDING

    # Auto-inspect local raster if file exists and format is GeoTIFF/COG
    if storage_path.is_file() and payload.format in {DatasetFormat.GEOTIFF, DatasetFormat.COG}:
        try:
            inspected = inspect_raster(storage_path)
            metadata = inspected
            crs = crs or inspected.get("crs")
            bounds = bounds or inspected.get("bounds")
            resolution = resolution or inspected.get("resolution")
            dimensions = dimensions or [inspected.get("width", 0), inspected.get("height", 0)]
            band_count = band_count or inspected.get("bands")
            if not checksum:
                checksum = _calculate_checksum(storage_path)
            validation_status = ValidationStatus.VALID
        except RasterValidationError as exc:
            validation_status = ValidationStatus.INVALID
            metadata = {"error": str(exc)}

    dataset = Dataset(
        project_id=payload.project_id,
        survey_id=payload.survey_id,
        name=payload.name,
        dataset_type=payload.dataset_type,
        format=payload.format,
        storage_uri=str(storage_path),
        crs=crs,
        bounds=bounds,
        resolution=resolution,
        dimensions=dimensions,
        band_count=band_count,
        gsd=gsd,
        checksum=checksum,
        validation_status=validation_status,
        validation_report=metadata if metadata else None,
        created_by=created_by,
    )
    db.add(dataset)
    db.commit()
    db.refresh(dataset)
    logger.info("Registered v2 dataset %s (%s, type=%s) for user %s", dataset.id, dataset.name, dataset.dataset_type, created_by)
    return dataset


def get_dataset(db: Session, dataset_id: uuid.UUID) -> Dataset:
    dataset = db.query(Dataset).filter_by(id=dataset_id).first()
    if not dataset:
        raise DatasetValidationError(f"Dataset '{dataset_id}' not found.")
    return dataset


def list_datasets(
    db: Session,
    project_id: uuid.UUID,
    dataset_type: DatasetType | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Dataset], int]:
    query = db.query(Dataset).filter_by(project_id=project_id)
    if dataset_type:
        query = query.filter_by(dataset_type=dataset_type)
    total = query.count()
    datasets = query.order_by(Dataset.created_at.desc()).offset(offset).limit(limit).all()
    return datasets, total


def validate_dataset(db: Session, dataset_id: uuid.UUID) -> DatasetValidationResult:
    dataset = get_dataset(db, dataset_id)
    storage_path = Path(dataset.storage_uri)
    report: dict[str, Any] = {"checks": []}
    is_valid = True

    if not storage_path.exists():
        is_valid = False
        report["checks"].append({"check": "file_exists", "status": "failed", "detail": f"File '{storage_path}' does not exist."})
    else:
        report["checks"].append({"check": "file_exists", "status": "passed"})
        # File format checks
        if dataset.format in {DatasetFormat.GEOTIFF, DatasetFormat.COG}:
            try:
                raster_meta = inspect_raster(storage_path)
                report["raster_metadata"] = raster_meta
                report["checks"].append({"check": "raster_structure", "status": "passed"})
                dataset.crs = raster_meta.get("crs")
                dataset.bounds = raster_meta.get("bounds")
                dataset.resolution = raster_meta.get("resolution")
                dataset.dimensions = [raster_meta.get("width", 0), raster_meta.get("height", 0)]
                dataset.band_count = raster_meta.get("bands")
            except RasterValidationError as exc:
                is_valid = False
                report["checks"].append({"check": "raster_structure", "status": "failed", "detail": str(exc)})

    status = ValidationStatus.VALID if is_valid else ValidationStatus.INVALID
    dataset.validation_status = status
    dataset.validation_report = report
    db.commit()
    db.refresh(dataset)

    return DatasetValidationResult(
        dataset_id=dataset.id,
        status=status,
        is_valid=is_valid,
        report=report,
    )
