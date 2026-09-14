"""Authenticated bounded reference-data provider and benchmark endpoints."""

import json
import uuid
import hashlib
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.v1.auth import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.models.user import User
from app.models.v2.project import Dataset, DatasetFormat, DatasetType, Project, ValidationStatus
from app.services.v2.quality.scorer import evaluate_cadastral_quality
from app.services.v2.reconciliation import reconcile_cadastral_parcels
from app.services.v2.reference_data import TelanganaArcGISReferenceProvider

router = APIRouter(prefix="/reference", tags=["v2 Reference Data"])


class BenchmarkRequest(BaseModel):
    project_id: uuid.UUID
    ai_features: list[dict[str, Any]] = Field(default_factory=list)
    reference_features: list[dict[str, Any]] = Field(default_factory=list)
    match_iou_threshold: float = Field(default=0.85, ge=0.5, le=1.0)
    minor_iou_threshold: float = Field(default=0.60, ge=0.3, le=0.9)


class BenchmarkResponse(BaseModel):
    project_id: str
    benchmark_status: str
    reconciliation_summary: dict[str, Any]
    quality_evaluation: dict[str, Any]
    reference_count: int
    ai_count: int


@router.get("/telangana/search")
def search_telangana_reference(
    min_lon: float = Query(..., ge=-180, le=180),
    min_lat: float = Query(..., ge=-90, le=90),
    max_lon: float = Query(..., ge=-180, le=180),
    max_lat: float = Query(..., ge=-90, le=90),
    current_user: User = Depends(get_current_user),
) -> dict:
    del current_user
    return TelanganaArcGISReferenceProvider().search([min_lon, min_lat, max_lon, max_lat])


@router.post("/telangana/save-dataset")
def save_telangana_reference_dataset(
    project_id: uuid.UUID = Query(...),
    min_lon: float = Query(..., ge=-180, le=180),
    min_lat: float = Query(..., ge=-90, le=90),
    max_lon: float = Query(..., ge=-180, le=180),
    max_lat: float = Query(..., ge=-90, le=90),
    dataset_name: str | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Fetch bounded Telangana reference parcels and register them as an authoritative
    EXISTING_PARCELS spatial dataset attached to the project.
    """
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

    bbox = [min_lon, min_lat, max_lon, max_lat]
    fc = TelanganaArcGISReferenceProvider().search(bbox)

    features = fc.get("features", [])
    if not features:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No reference parcels found in specified bounds.")

    out_dir = Path(settings.V2_DATASET_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)
    filename = f"telangana_ref_{project_id}_{uuid.uuid4().hex[:8]}.geojson"
    file_path = out_dir / filename

    raw_json = json.dumps(fc, indent=2)
    file_path.write_text(raw_json, encoding="utf-8")
    checksum = hashlib.sha256(raw_json.encode("utf-8")).hexdigest()

    name = dataset_name or f"Telangana Reference Parcels ({len(features)})"
    dataset = Dataset(
        project_id=project_id,
        name=name,
        dataset_type=DatasetType.EXISTING_PARCELS,
        format=DatasetFormat.GEOJSON,
        storage_uri=str(file_path.as_posix()),
        crs="EPSG:4326",
        bounds=bbox,
        checksum=checksum,
        validation_status=ValidationStatus.VALID,
        validation_report={
            "feature_count": len(features),
            "provider": "telangana_tgrac_arcgis",
            "source_url": fc.get("source_url"),
        },
        created_by=current_user.id,
    )
    db.add(dataset)
    db.commit()
    db.refresh(dataset)

    return {
        "dataset_id": str(dataset.id),
        "name": dataset.name,
        "feature_count": len(features),
        "storage_uri": dataset.storage_uri,
        "validation_status": dataset.validation_status.value,
        "features": features,
    }


@router.post("/benchmark", response_model=BenchmarkResponse)
def compute_reference_benchmark(
    payload: BenchmarkRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BenchmarkResponse:
    """
    Compute an honest reference accuracy benchmark between authoritative reference parcels
    and AI-extracted features for the specified project.
    """
    del current_user
    project = db.query(Project).filter(Project.id == payload.project_id).first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

    if not payload.reference_features:
        return BenchmarkResponse(
            project_id=str(payload.project_id),
            benchmark_status="NOT_EVALUATED",
            reconciliation_summary={"message": "No authoritative reference parcels provided for benchmark."},
            quality_evaluation={"status": "Not evaluated", "score": 0.0},
            reference_count=0,
            ai_count=len(payload.ai_features),
        )

    recon_report = reconcile_cadastral_parcels(
        existing_parcels=payload.reference_features,
        ai_parcels=payload.ai_features,
        match_iou_threshold=payload.match_iou_threshold,
        minor_iou_threshold=payload.minor_iou_threshold,
    )
    recon_dict = recon_report.to_dict()

    confidences = [
        float(f.get("properties", {}).get("confidence") or f.get("properties", {}).get("confidence_score", 0.75))
        for f in payload.ai_features
    ]
    mean_conf = sum(confidences) / len(confidences) if confidences else 0.75

    quality = evaluate_cadastral_quality(
        total_features=len(payload.ai_features),
        mean_ai_confidence=mean_conf,
        reconciliation_summary=recon_dict.get("summary"),
    )

    return BenchmarkResponse(
        project_id=str(payload.project_id),
        benchmark_status="EVALUATED",
        reconciliation_summary=recon_dict,
        quality_evaluation=quality.to_dict(),
        reference_count=len(payload.reference_features),
        ai_count=len(payload.ai_features),
    )