"""Authenticated bounded reference-data provider endpoints."""

from fastapi import APIRouter, Depends, Query

from app.api.v1.auth import get_current_user
from app.models.user import User
from app.services.v2.reference_data import TelanganaArcGISReferenceProvider

router = APIRouter(prefix="/reference", tags=["v2 Reference Data"])


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