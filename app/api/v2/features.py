"""V2 capability and cadastral feature contract endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from pathlib import Path

from app.api.v1.auth import get_current_user
from app.models.user import User
from app.core.config import settings
from app.schemas.features import (
    FeatureExtractionRequest,
    FeatureExtractionResponse,
    V2Capability,
    V2CapabilityManifest,
)
from app.services.v2.feature_extraction import FeatureExtractionError, extract_features

router = APIRouter(prefix="/features", tags=["v2 Feature Layers"])


@router.get("/manifest", response_model=V2CapabilityManifest)
def get_v2_capability_manifest(
    current_user: User = Depends(get_current_user),
) -> V2CapabilityManifest:
    """Describe which PS 26012 feature layers are implemented or planned."""
    del current_user
    return V2CapabilityManifest(
        capabilities=[
            V2Capability(
                layer="parcel",
                status="available",
                description="SAM-compatible parcel extraction and topology quality checks.",
            ),
            V2Capability(
                layer="building",
                status="available",
                description="Preliminary building footprint layer from raster segmentation baseline.",
            ),
            V2Capability(
                layer="road",
                status="available",
                description="Preliminary road layer from raster segmentation baseline.",
            ),
            V2Capability(
                layer="access_corridor",
                status="available",
                description="Preliminary access-corridor layer from raster segmentation baseline.",
            ),
            V2Capability(
                layer="land_use",
                status="available",
                description="Reviewable land-use candidate layer from raster segmentation baseline.",
            ),
        ]
    )


@router.post("/extract", response_model=FeatureExtractionResponse)
def extract_feature_layer(
    payload: FeatureExtractionRequest,
    current_user: User = Depends(get_current_user),
) -> FeatureExtractionResponse:
    """Generate a preliminary review layer from a published v2 raster asset."""
    del current_user
    asset = Path(settings.V2_RASTER_DIR).resolve() / payload.asset_id
    if asset.name != payload.asset_id or asset.suffix.lower() not in {".tif", ".tiff"}:
        raise HTTPException(status_code=400, detail="Invalid raster asset id.")
    if not asset.is_file():
        raise HTTPException(status_code=404, detail="Raster asset not found.")
    try:
        features = extract_features(asset, payload.layer, payload.threshold_percentile)
    except FeatureExtractionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return FeatureExtractionResponse(
        layer=payload.layer,
        source_asset_id=payload.asset_id,
        model="raster-threshold-baseline/v2.0",
        features=features,
    )
