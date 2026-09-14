"""
app/models/v2/project.py
------------------------
Relational data model for cadastral survey hierarchy in BhuDrishti V2:
Project -> Survey -> Dataset.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    DateTime,
    Enum as SQLEnum,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ProjectStatus(str, enum.Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    COMPLETED = "completed"


class SurveyMethod(str, enum.Enum):
    DRONE_AERIAL = "drone_aerial"
    SATELLITE = "satellite"
    HYBRID = "hybrid"
    GROUND_TRUTH = "ground_truth"


class DatasetType(str, enum.Enum):
    ORI = "ORI"                     # Orthorectified Imagery
    DSM = "DSM"                     # Digital Surface Model
    DTM = "DTM"                     # Digital Terrain Model
    DEM = "DEM"                     # Digital Elevation Model
    EXISTING_PARCELS = "EXISTING_PARCELS"  # Historical cadastral vector map
    GT = "GT"                       # Ground Truth verification points/features
    GNSS = "GNSS"                   # Global Navigation Satellite System points
    CORS = "CORS"                   # CORS baseline/correction data
    BUILDING_LAYER = "BUILDING_LAYER"
    ROAD_LAYER = "ROAD_LAYER"
    FEATURE_MAP = "FEATURE_MAP"
    OTHER = "OTHER"


class DatasetFormat(str, enum.Enum):
    GEOTIFF = "GeoTIFF"
    COG = "COG"
    GEOJSON = "GeoJSON"
    SHAPEFILE = "Shapefile"
    GEOPACKAGE = "GeoPackage"
    CSV = "CSV"
    OTHER = "OTHER"


class ValidationStatus(str, enum.Enum):
    PENDING = "pending"
    VALID = "valid"
    INVALID = "invalid"


class Project(Base):
    """Represents an administrative survey project (e.g. ULB or Tehsil land survey)."""

    __tablename__ = "v2_projects"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    state: Mapped[str] = mapped_column(String(64), nullable=False)
    district: Mapped[str] = mapped_column(String(64), nullable=False)
    ulb: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[ProjectStatus] = mapped_column(
        SQLEnum(
            ProjectStatus,
            name="v2_project_status_enum",
            values_callable=lambda statuses: [s.value for s in statuses],
        ),
        nullable=False,
        default=ProjectStatus.ACTIVE,
        index=True,
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utc_now, onupdate=_utc_now, nullable=False
    )

    # Relationships
    surveys: Mapped[list[Survey]] = relationship(
        "Survey", back_populates="project", cascade="all, delete-orphan"
    )
    datasets: Mapped[list[Dataset]] = relationship(
        "Dataset", back_populates="project", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_v2_projects_state_district_ulb", "state", "district", "ulb"),
    )


class Survey(Base):
    """Represents a survey campaign / survey unit within an administrative project."""

    __tablename__ = "v2_surveys"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("v2_projects.id"), nullable=False, index=True
    )
    survey_unit: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    survey_method: Mapped[SurveyMethod] = mapped_column(
        SQLEnum(
            SurveyMethod,
            name="v2_survey_method_enum",
            values_callable=lambda methods: [m.value for m in methods],
        ),
        nullable=False,
        default=SurveyMethod.DRONE_AERIAL,
    )
    survey_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    metadata_info: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utc_now, onupdate=_utc_now, nullable=False
    )

    project: Mapped[Project] = relationship("Project", back_populates="surveys")
    datasets: Mapped[list[Dataset]] = relationship("Dataset", back_populates="survey")


class Dataset(Base):
    """
    Represents any registered spatial input/output asset.
    Stores metadata, footprints, and validation status. Large binaries are stored
    in object/file storage, never as database blobs.
    """

    __tablename__ = "v2_datasets"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("v2_projects.id"), nullable=False, index=True
    )
    survey_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("v2_surveys.id"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    dataset_type: Mapped[DatasetType] = mapped_column(
        SQLEnum(
            DatasetType,
            name="v2_dataset_type_enum",
            values_callable=lambda types: [t.value for t in types],
        ),
        nullable=False,
        index=True,
    )
    format: Mapped[DatasetFormat] = mapped_column(
        SQLEnum(
            DatasetFormat,
            name="v2_dataset_format_enum",
            values_callable=lambda formats: [f.value for f in formats],
        ),
        nullable=False,
    )
    crs: Mapped[str | None] = mapped_column(String(64), nullable=True)
    bounds: Mapped[list[float] | None] = mapped_column(JSON, nullable=True)
    resolution: Mapped[list[float] | None] = mapped_column(JSON, nullable=True)
    dimensions: Mapped[list[int] | None] = mapped_column(JSON, nullable=True)
    band_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gsd: Mapped[float | None] = mapped_column(Float, nullable=True)
    storage_uri: Mapped[str] = mapped_column(String(512), nullable=False)
    checksum: Mapped[str | None] = mapped_column(String(64), nullable=True)
    validation_status: Mapped[ValidationStatus] = mapped_column(
        SQLEnum(
            ValidationStatus,
            name="v2_validation_status_enum",
            values_callable=lambda statuses: [s.value for s in statuses],
        ),
        nullable=False,
        default=ValidationStatus.PENDING,
        index=True,
    )
    validation_report: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, nullable=True
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utc_now, onupdate=_utc_now, nullable=False
    )

    project: Mapped[Project] = relationship("Project", back_populates="datasets")
    survey: Mapped[Survey | None] = relationship("Survey", back_populates="datasets")

    __table_args__ = (
        Index("idx_v2_datasets_project_type", "project_id", "dataset_type"),
    )
